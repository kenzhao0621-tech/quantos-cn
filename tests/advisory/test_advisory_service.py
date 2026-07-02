"""AdvisoryService integration tests on a synthetic DuckDB warehouse.

Builds ~80 trading days for 30 synthetic symbols so cross-sectional
normalization is meaningful, then checks the full card contract: provenance,
formula version, cache hit on second call, invalidation on new bars, honest
missing-factor handling, and forbidden-language cleanliness.
"""

import json
import math

import pytest

duckdb = pytest.importorskip("duckdb")

from quant.application.advisory_service import AdvisoryService
from quant.cache_os.metrics import CacheMetrics
from quant.cache_os.policy import CachePolicyRegistry
from quant.cache_os.registry import CacheRegistry
from quant.explain_os.language_guard import FORBIDDEN_PHRASES

from quant.scoring_os.weights import SCORE_WEIGHT_VERSION

N_DAYS = 80
SYMBOLS = [f"6{i:05d}.SH" for i in range(30)]
TARGET = SYMBOLS[0]


def _unwrap(card):
    """v2.3 advise() returns envelope; tests target the explain card."""
    return card.get("explain") or card


def _build_warehouse(path, extra_day=False):
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE IF NOT EXISTS daily_bars (
            ts_code VARCHAR, trade_date DATE, open DOUBLE, high DOUBLE, low DOUBLE,
            close DOUBLE, pre_close DOUBLE, change DOUBLE, pct_chg DOUBLE,
            vol DOUBLE, amount DOUBLE, month VARCHAR, year VARCHAR)
    """)
    con.execute("DELETE FROM daily_bars")
    rows = []
    days = N_DAYS + (1 if extra_day else 0)
    for si, sym in enumerate(SYMBOLS):
        price = 10.0 + si * 0.5
        for d in range(days):
            # deterministic pseudo-random walk, different drift per symbol
            drift = 0.0005 * (si - 15) + 0.002 * math.sin(d / 7.0 + si)
            prev = price
            price = max(1.0, price * (1 + drift))
            date = f"2026-{3 + d // 28:02d}-{d % 28 + 1:02d}"
            rows.append((sym, date, prev, max(prev, price) * 1.01,
                         min(prev, price) * 0.99, price, prev,
                         price - prev, (price / prev - 1) * 100,
                         1e6 + si * 1e4, 5e4 + si * 2e3, date[5:7], date[:4]))
    con.executemany("INSERT INTO daily_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.execute("""
        CREATE TABLE IF NOT EXISTS industry_map (
            code VARCHAR, name VARCHAR, sector_code VARCHAR, sector_name VARCHAR, source VARCHAR)
    """)
    con.execute("DELETE FROM industry_map")
    con.executemany(
        "INSERT INTO industry_map VALUES (?,?,?,?,?)",
        [(s, f"股票{i}", f"S{i % 3}", ["半导体", "银行", "医药"][i % 3], "tushare")
         for i, s in enumerate(SYMBOLS)])
    con.execute("""
        CREATE TABLE IF NOT EXISTS fundamental (
            ts_code VARCHAR, trade_date DATE, pe_ttm DOUBLE, pb DOUBLE, ps DOUBLE,
            turnover_rate DOUBLE, dv_ttm DOUBLE, total_mv DOUBLE, circ_mv DOUBLE, source VARCHAR)
    """)
    con.execute("DELETE FROM fundamental")
    con.executemany(
        "INSERT INTO fundamental VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(s, "2026-06-26", 15.0 + i, 1.5, 2.0, 3.0 + i * 0.1, 1.0, 5e5, 3e5, "tushare")
         for i, s in enumerate(SYMBOLS)])
    con.close()


@pytest.fixture()
def service(tmp_path):
    wh = tmp_path / "quant.duckdb"
    _build_warehouse(wh)
    svc = AdvisoryService(warehouse=wh)
    svc.cache = CacheRegistry(
        policy_registry=CachePolicyRegistry(warehouse=wh),
        disk_dir=tmp_path / "cache",
    )
    svc.cache.metrics = CacheMetrics()
    return svc


def test_card_contract(service):
    card = _unwrap(service.advise(TARGET, capital_cny=20000, include_kronos=False))
    assert not card.get("blocked")
    h = card["headline"]
    assert h["score_weight_version"] == SCORE_WEIGHT_VERSION
    assert h["cache_status"] in ("cache_miss", "cache_hit", "force_refresh")
    assert h["data_freshness"]
    assert h["updated_at"]
    # four panels
    assert card["panel_a_verified_facts"], "must have verified facts"
    for f in card["panel_a_verified_facts"]:
        assert f["source_url"] and f["updated_at"]
    bd = card["panel_b_quant_computation"]
    assert bd["score_weight_version"] == SCORE_WEIGHT_VERSION
    assert len(bd["factors"]) == 8
    plan = card["panel_d_conditional_advice"]["trade_plan"]
    assert plan["recommendation"] in ("buy_zone", "watch", "avoid", "insufficient_structure")
    assert card["panel_d_conditional_advice"]["do_not_buy_conditions"] or plan["do_not_buy_conditions"]
    assert card["disclaimer"]
    assert card["cache"]["cache_status"]


def test_missing_sources_reported_not_fabricated(service):
    card = _unwrap(service.advise(TARGET, include_kronos=False, include_agents=False))
    missing = card["panel_b_quant_computation"]["missing_factors"]
    # no kronos model and no sentiment source on this branch
    assert "kronos_forecast" in missing
    assert "sentiment" in missing
    rows = {r["factor"]: r for r in card["panel_b_quant_computation"]["factors"]}
    assert rows["kronos_forecast"]["missing"] and rows["kronos_forecast"]["score"] == 50.0


def test_second_call_hits_cache(service):
    a = _unwrap(service.advise(TARGET, include_kronos=False, include_agents=False))
    b = _unwrap(service.advise(TARGET, include_kronos=False, include_agents=False))
    assert a["headline"]["cache_status"] in ("cache_miss",)
    assert b["headline"]["cache_status"] == "cache_hit"
    snap = service.cache.metrics.snapshot()
    assert snap["cache_summary"]["hit_count"] >= 1


def test_force_refresh_bypasses(service):
    service.advise(TARGET, include_kronos=False, include_agents=False)
    c = _unwrap(service.advise(TARGET, force_refresh=True, include_kronos=False, include_agents=False))
    assert c["headline"]["cache_status"] == "force_refresh"


def test_new_bar_invalidates_advisory(service, tmp_path):
    a = _unwrap(service.advise(TARGET, include_kronos=False, include_agents=False))
    _build_warehouse(service.warehouse, extra_day=True)  # a new trading day lands
    b = _unwrap(service.advise(TARGET, include_kronos=False, include_agents=False))
    assert b["headline"]["cache_status"] == "cache_miss"  # data_version changed
    assert b["as_of_date"] >= a["as_of_date"]


def test_different_capital_different_cache_entry(service):
    a = _unwrap(service.advise(TARGET, capital_cny=5000, include_kronos=False, include_agents=False))
    b = _unwrap(service.advise(TARGET, capital_cny=100000, include_kronos=False, include_agents=False))
    assert a["headline"]["cache_status"] == "cache_miss"
    assert b["headline"]["cache_status"] == "cache_miss"  # params in key


def test_unknown_symbol_blocked_honestly(service):
    card = service.advise("999999.SH")
    assert card["blocked"]
    assert "999999.SH" in card["blocker_reason"] or "未找到" in card["blocker_reason"]


def test_card_language_clean(service):
    card = _unwrap(service.advise(TARGET, include_kronos=False, include_agents=False))
    card.pop("language_guard_violations", None)
    blob = json.dumps(card, ensure_ascii=False, default=str)
    assert not any(p in blob for p in FORBIDDEN_PHRASES)


def test_audit_report_written(service):
    card = _unwrap(service.advise(TARGET, include_kronos=False, include_agents=False))
    audit = card.get("audit") or {}
    assert audit.get("run_id")


def test_reproducible_same_inputs(service):
    a = _unwrap(service.advise(TARGET, force_refresh=True, include_kronos=False, include_agents=False))
    b = _unwrap(service.advise(TARGET, force_refresh=True, include_kronos=False, include_agents=False))
    assert a["panel_b_quant_computation"]["final_score"] == b["panel_b_quant_computation"]["final_score"]
    assert a["panel_b_quant_computation"]["factors"] == b["panel_b_quant_computation"]["factors"]
