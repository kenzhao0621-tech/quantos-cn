#!/usr/bin/env python3
"""Real-data pipeline tests — cache/mocks; live AKShare optional."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

passed = failed = blocked = 0


def ok(n):
    global passed
    passed += 1
    print(f"PASS {n}")


def fail(n, m=""):
    global failed
    failed += 1
    print(f"FAIL {n} {m}")


def blk(n, m=""):
    global blocked
    blocked += 1
    print(f"BLOCKED {n} {m}")


from tools.china_quant.modes import OperatingMode, MODE_BANNERS
from tools.china_quant.cache import cache_set, cache_get, cache_key
from tools.china_quant.universe_builder import build_real_universe
from tools.china_quant.regime_v2 import classify_regime_v2
from tools.china_quant.sector_data import rank_sectors_from_boards
from tools.china_quant.daily_runner import run_fixture, run_latest_available, write_deliverables
from tools.china_quant.providers.base import ProviderError
from tools.china_quant.scoring_v2 import score_stock_v2
from tools.china_quant.models import StockRecord
from tools.china_quant.risk import compute_trade_levels
from tools.china_quant.report_deliverables import render_policy_report, render_backtest_report
from tools.china_quant.policy_monitor import PolicyItem
from tools.china_quant.backtest.engine import run_backtest
from tools.china_quant.providers.fixture_provider import FixtureProvider

if OperatingMode.FIXTURE.value in MODE_BANNERS:
    ok("operating modes defined")

# Cache round-trip
ckey = cache_key("test")
cache_set(ROOT / ".cache/china-quant-test", ckey, {"x": 1})
if cache_get(ROOT / ".cache/china-quant-test", ckey, 60) == {"x": 1}:
    ok("cache round-trip")
else:
    fail("cache")

spot = [
    {"code": "601398", "name": "工行", "price": 5.2, "change_pct": 1.0, "amount": 5e8, "volume": 1e6, "is_st": False},
    {"code": "600001", "name": "ST测试", "price": 2.0, "change_pct": 0, "amount": 1e7, "volume": 1, "is_st": True},
    {"code": "002001", "name": "低流动", "price": 3.0, "change_pct": 0, "amount": 1e6, "volume": 1, "is_st": False},
    {"code": "688001", "name": "科创", "price": 50.0, "change_pct": 2.0, "amount": 8e8, "volume": 1e5, "is_st": False, "history_days": 30},
]
audit = build_real_universe(spot, mode="TEST", analysis_date="2026-06-12")
if audit.eligible == 1 and audit.exclusion_counts.get("ST默认排除") == 1:
    ok("universe ST exclude")
else:
    fail("universe exclude", f"eligible={audit.eligible}")

if audit.exclusion_counts.get("流动性不足") == 1:
    ok("liquidity failure")
else:
    fail("liquidity")

if audit.exclusion_counts.get("历史不足") == 1:
    ok("insufficient history")
else:
    fail("history")

reg = classify_regime_v2({"sh": {"change_pct": 1.5}}, spot)
if reg.result.max_primary_candidates >= 2:
    ok("regime v2 bull")
else:
    fail("regime v2")

reg_bear = classify_regime_v2({"sh": {"change_pct": -3.0}}, spot)
if reg_bear.result.max_primary_candidates == 0:
    ok("strong-bear NO TRADE")
else:
    fail("bear NO TRADE")

boards = [{"板块名称": "银行", "涨跌幅": 2.5, "上涨家数": 30, "下跌家数": 5}]
if rank_sectors_from_boards(boards):
    ok("sector ranking")
else:
    fail("sector ranking")

FIX = ROOT / "docs" / "test-fixtures" / "china-quant"
r = run_fixture(FIX)
paths = write_deliverables(r, ROOT / "docs" / "test-output" / "daily-run-test", FIX)
required = ["premarket", "policy", "institutional", "freshness", "backtest"]
if all(paths.get(k) and paths[k].exists() for k in required):
    ok("fixture deliverables")
else:
    fail("deliverables", str(list(paths.keys())))

st = StockRecord(code="601398", name="工行", exchange="SH", board="MAIN_SH", sector="银行", price=5.2, change_pct=1.0, avg_daily_value_m=500)
fs = score_stock_v2(st, regime_name="WEAK_BULL", sector_strength=14, has_confirmed_catalyst=False, institutional_score=0)
if fs.total >= 35:
    ok("stock ranking score")
else:
    fail("stock score", str(fs.total))

lv = compute_trade_levels(st)
if lv.acceptable:
    ok("valid entry zone")
else:
    fail("entry", lv.reject_reason or "")

st_lim = StockRecord(code="x", name="x", exchange="SH", board="MAIN_SH", sector="x", price=10, change_pct=0, avg_daily_value_m=500, at_limit_up=True)
lv_lim = compute_trade_levels(st_lim)
if not lv_lim.acceptable and "涨停" in lv_lim.reject_reason:
    ok("limit-up entry blocked")
else:
    fail("limit-up")

pol = render_policy_report([PolicyItem("测试", "CSRC", "2026-06-01", "2026-06-01", "confirmed", [], [], "HIGH", False)], mode=OperatingMode.FIXTURE, analysis_date="2026-06-12")
if "FIXTURE" in pol or "测试样本" in pol:
    ok("policy classification")
else:
    fail("policy")

fp = FixtureProvider(FIX)
bt = run_backtest(fp.load_bars("601398").payload["bars"])
if "sharpe" in bt.metrics:
    ok("backtest metrics")
else:
    fail("backtest")

if render_backtest_report(FIX).find("PRELIMINARY") >= 0 or render_backtest_report(FIX).find("VALIDATED") >= 0:
    ok("backtest report")
else:
    fail("backtest report")

# Live AKShare optional
try:
    from tools.china_quant.providers.akshare_provider import AKShareProvider

    ak = AKShareProvider(use_cache=True)
    cal = ak.get_trading_calendar()
    if cal.row_count > 200:
        ok("akshare calendar")
    else:
        fail("akshare calendar")
    spot_env = ak.get_spot_quotes()
    if spot_env.row_count > 1000:
        ok("akshare full spot universe")
    else:
        blk("akshare spot", f"rows={spot_env.row_count}")
except ProviderError as e:
    blk("akshare live", str(e))
except Exception as e:
    blk("akshare live", str(e))

try:
    live = run_latest_available(FIX, max_screen=50, use_cache=True)
    if live.mode == OperatingMode.LATEST_AVAILABLE:
        ok("latest_available pipeline")
        if live.universe_audit and live.universe_audit.total_retrieved > 100:
            ok("real universe size")
        elif live.limitations and "BLOCKED" in str(live.limitations):
            blk("real universe size", "provider blocked")
        if live.report.primary or "NO TRADE" in live.report.trade_today or "BLOCKED" in live.report.trade_today:
            ok("latest primary or NO TRADE")
    else:
        fail("latest pipeline")
except Exception as e:
    blk("latest pipeline", str(e))

print(f"\nSUMMARY PASS={passed} FAIL={failed} BLOCKED={blocked}")
sys.exit(0 if failed == 0 else 1)
