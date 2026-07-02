"""v2.2 §3 / §12.1 acceptance: TTL table, session switching, freshness states."""

from datetime import datetime

from quant.cache_os.freshness import FreshnessStatus, evaluate_freshness
from quant.cache_os.policy import CachePolicyRegistry, ResolvedPolicy
from quant.freshness_contract import CST

TRADING = datetime(2026, 7, 1, 10, 0, tzinfo=CST)      # Wednesday 10:00 — open
NON_TRADING = datetime(2026, 7, 1, 20, 0, tzinfo=CST)  # Wednesday 20:00 — closed
WEEKEND = datetime(2026, 7, 4, 10, 0, tzinfo=CST)      # Saturday


def _registry(tmp_path):
    # Point at a missing warehouse: calendar degrades to weekday approximation.
    return CachePolicyRegistry(warehouse=tmp_path / "missing.duckdb")


def test_ttl_switches_between_trading_and_non_trading(tmp_path):
    reg = _registry(tmp_path)
    quote_trading = reg.resolve("realtime_quote", now=TRADING)
    quote_night = reg.resolve("realtime_quote", now=NON_TRADING)
    assert quote_trading.ttl_seconds == 20
    assert quote_night.ttl_seconds == 900
    assert quote_trading.is_trading and not quote_night.is_trading


def test_weekend_uses_non_trading_ttl(tmp_path):
    reg = _registry(tmp_path)
    assert reg.resolve("advisory_result", now=WEEKEND).ttl_seconds == 7200


def test_default_ttl_table_matches_spec(tmp_path):
    reg = _registry(tmp_path)
    expect_trading = {
        "realtime_quote": 20, "intraday_bar": 45, "ohlcv_daily": 600,
        "announcement": 600, "policy_news": 3600, "sector_strength": 120,
        "money_flow": 180, "sentiment_news": 600, "kronos_prediction": 600,
        "agents_research": 1800, "advisory_result": 600,
    }
    for dtype, ttl in expect_trading.items():
        assert reg.resolve(dtype, now=TRADING).ttl_seconds == ttl, dtype
    assert reg.resolve("adjustment_factor", now=TRADING).ttl_seconds == 86400
    assert reg.resolve("financial_statement", now=NON_TRADING).ttl_seconds == 86400


def test_backtest_result_cached_by_params_hash_no_ttl(tmp_path):
    reg = _registry(tmp_path)
    p = reg.resolve("backtest_result", now=TRADING)
    assert p.ttl_seconds is None
    assert p.cache_by_params_hash


def test_calendar_degraded_when_no_trade_calendar(tmp_path):
    reg = _registry(tmp_path)
    assert reg.session_state(now=TRADING)["calendar_status"] == "degraded"


def test_feature_vector_invalidates_on_underlying_change(tmp_path):
    reg = _registry(tmp_path)
    assert reg.resolve("feature_vector", now=TRADING).invalidate_on_underlying_change


def _policy(ttl, stale_mult=3.0):
    return ResolvedPolicy(
        data_type="test", ttl_seconds=ttl, session="open_morning", is_trading=True,
        calendar_status="degraded", stale_allowed_seconds=(ttl * stale_mult) if ttl else None,
    )


def test_freshness_fresh_within_ttl():
    r = evaluate_freshness(stored_at=1000.0, policy=_policy(60), now=1030.0)
    assert r.status is FreshnessStatus.FRESH
    assert r.usable_for_recommendation


def test_freshness_stale_allowed_after_ttl():
    r = evaluate_freshness(stored_at=1000.0, policy=_policy(60), now=1100.0)
    assert r.status is FreshnessStatus.STALE_ALLOWED
    assert not r.usable_for_recommendation


def test_freshness_expired_after_grace():
    r = evaluate_freshness(stored_at=1000.0, policy=_policy(60), now=1000.0 + 200)
    assert r.status is FreshnessStatus.EXPIRED
    assert not r.usable_for_recommendation


def test_freshness_degraded_flag_propagates():
    r = evaluate_freshness(stored_at=1000.0, policy=_policy(60), degraded=True, now=1010.0)
    assert r.status is FreshnessStatus.DEGRADED
    assert r.usable_for_recommendation  # usable but must be labelled


def test_freshness_unavailable_when_missing():
    r = evaluate_freshness(stored_at=None, policy=_policy(60))
    assert r.status is FreshnessStatus.UNAVAILABLE
    assert not r.usable_for_recommendation


def test_params_hash_cache_never_time_expires():
    r = evaluate_freshness(stored_at=0.0, policy=_policy(None), now=10**9)
    assert r.status is FreshnessStatus.FRESH
