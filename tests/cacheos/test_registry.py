"""v2.2 §12.1 acceptance: hit/miss, force refresh bypass, stale-on-failure, metrics."""

import pytest

from quant.cache_os.cache_key import CacheKey
from quant.cache_os.freshness import FreshnessStatus
from quant.cache_os.metrics import CacheMetrics
from quant.cache_os.policy import CachePolicyRegistry
from quant.cache_os.prediction_cache import PredictionCache
from quant.cache_os.registry import CacheRegistry


@pytest.fixture()
def registry(tmp_path):
    reg = CacheRegistry(
        policy_registry=CachePolicyRegistry(warehouse=tmp_path / "missing.duckdb"),
        disk_dir=tmp_path / "cache",
    )
    reg.metrics = CacheMetrics()  # isolate metrics per test
    return reg


def _key(**kw):
    base = dict(data_type="advisory_result", symbol="600519.SH", as_of_date="2026-07-01")
    base.update(kw)
    return CacheKey(**base)


def test_miss_then_hit_without_recompute(registry):
    calls = []

    def loader():
        calls.append(1)
        return {"score": 73.2}, {"source": "tushare", "updated_at": "2026-07-01 15:00:00"}

    first = registry.get_or_compute(_key(), loader)
    second = registry.get_or_compute(_key(), loader)
    assert first.cache_status == "miss"
    assert second.cache_status == "hit"
    assert second.value == {"score": 73.2}
    assert second.source == "tushare"
    assert len(calls) == 1


def test_force_refresh_bypasses_cache(registry):
    calls = []
    loader = lambda: calls.append(1) or {"v": len(calls)}
    registry.get_or_compute(_key(), loader)
    res = registry.get_or_compute(_key(), loader, force_refresh=True)
    assert res.cache_status == "force_refresh"
    assert len(calls) == 2


def test_loader_failure_falls_back_to_stale(registry):
    ok = lambda: {"v": 1}
    registry.get_or_compute(_key(), ok)

    def boom():
        raise RuntimeError("origin down")

    res = registry.get_or_compute(_key(), boom, force_refresh=True)
    assert res.cache_status == "stale_allowed"
    assert res.value == {"v": 1}
    assert res.freshness.status is FreshnessStatus.DEGRADED or res.freshness.status is FreshnessStatus.FRESH
    assert "loader_error" in res.meta


def test_loader_failure_without_cache_is_unavailable(registry):
    def boom():
        raise RuntimeError("origin down")

    res = registry.get_or_compute(_key(symbol="000001.SZ"), boom)
    assert res.cache_status == "unavailable"
    assert res.value is None
    assert res.freshness.status is FreshnessStatus.UNAVAILABLE
    assert not res.freshness.usable_for_recommendation


def test_disk_persistence_survives_memory_clear(registry):
    loader = lambda: {"v": 42}
    registry.get_or_compute(_key(), loader, persist=True)
    registry.memory.clear()
    res = registry.get_or_compute(_key(), lambda: pytest.fail("should hit disk"), persist=True)
    assert res.cache_status == "hit"
    assert res.value == {"v": 42}


def test_metrics_hit_rate_recorded(registry):
    loader = lambda: {"v": 1}
    registry.get_or_compute(_key(), loader)
    registry.get_or_compute(_key(), loader)
    registry.get_or_compute(_key(), loader)
    snap = registry.metrics.snapshot()
    assert snap["cache_summary"]["hit_count"] == 2
    assert snap["cache_summary"]["miss_count"] == 1
    assert snap["cache_summary"]["hit_rate"] == pytest.approx(2 / 3, abs=1e-4)


def test_invalidate_removes_entry(registry):
    loader_calls = []
    loader = lambda: loader_calls.append(1) or {"v": 1}
    registry.get_or_compute(_key(), loader)
    assert registry.invalidate(_key())
    registry.get_or_compute(_key(), loader)
    assert len(loader_calls) == 2


def test_prediction_cache_keyed_by_data_version(registry):
    cache = PredictionCache(registry)
    calls = []

    def predictor():
        calls.append(1)
        return {"direction_prob": 0.6, "expected_return": 0.01, "confidence": 0.55}

    kw = dict(model="kronos-mini", symbol="600519.SH", horizon="5d", predictor=predictor)
    a = cache.get_or_predict(data_version="2026-07-01:696125", **kw)
    b = cache.get_or_predict(data_version="2026-07-01:696125", **kw)
    assert a.cache_status == "miss" and b.cache_status == "hit"
    assert len(calls) == 1
    # New K-line arrived → new data_version → recompute
    c = cache.get_or_predict(data_version="2026-07-02:701000", **kw)
    assert c.cache_status == "miss"
    assert len(calls) == 2


def test_prediction_cache_distinguishes_model_and_horizon(registry):
    cache = PredictionCache(registry)
    n = {"count": 0}

    def predictor():
        n["count"] += 1
        return {"v": n["count"]}

    base = dict(symbol="600519.SH", data_version="v1", predictor=predictor)
    cache.get_or_predict(model="kronos-mini", horizon="5d", **base)
    cache.get_or_predict(model="kronos-small", horizon="5d", **base)
    cache.get_or_predict(model="kronos-mini", horizon="10d", **base)
    assert n["count"] == 3
