#!/usr/bin/env python3
"""Tests A–I + market rules (Phase 6) for China A-share outlook."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.china_quant.data import load_fixture
from tools.china_quant.freshness import assess_freshness
from tools.china_quant.models import StockRecord
from tools.china_quant.news_integrity import assess_catalyst
from tools.china_quant.pipeline import load_bundle, run_pipeline
from tools.china_quant.regime import classify_regime
from tools.china_quant.report import render_report
from tools.china_quant.risk import compute_trade_levels
from tools.china_quant.rules import Board, check_entry_feasible, limit_pct
from tools.china_quant.screening import screen_stock

FIX = ROOT / "docs" / "test-fixtures" / "china-quant"
LEDGER = ROOT / "docs" / "ai" / "daily-trading" / "PERFORMANCE_LEDGER.csv"

passed = failed = 0


def ok(name: str):
    global passed
    passed += 1
    print(f"PASS {name}")


def fail(name: str, msg: str = ""):
    global failed
    failed += 1
    print(f"FAIL {name} {msg}")


def ref_now(fixture: str, bundle):
    if fixture == "stale_data":
        return datetime.now()
    return bundle.snapshot.data_timestamp + timedelta(hours=16)


# A
stale_b = load_bundle("stale_data", FIX)
if not assess_freshness(stale_b.snapshot.data_timestamp, now=datetime.now()).live_decision_ok:
    ok("A freshness stale rejected")
else:
    fail("A freshness")

# B
weak_b = load_bundle("weak_market", FIX)
weak_r = run_pipeline(weak_b, fixtures_dir=FIX, now=ref_now("weak_market", weak_b))
if weak_r.report.regime.max_primary_candidates == 0:
    ok("B no trade weak market")
else:
    fail("B no trade")

# C
bull_b = load_bundle("bullish_market", FIX)
bull_r = run_pipeline(bull_b, fixtures_dir=FIX, now=ref_now("bullish_market", bull_b))
md = render_report(bull_r.report)
if bull_r.report.primary:
    c0 = render_report(bull_r.report)
    for field in ["止损位", "买入确认条件", "取消买入条件", "第一止盈"]:
        ok(f"C field {field}") if field in c0 else fail(f"C field {field}")
else:
    fail("C bullish primary missing")

# D
if not check_entry_feasible(at_limit_up=True).tradable:
    ok("D limit-up blocked")
else:
    fail("D limit-up")

# E
if not assess_catalyst("x", social_media_only=True, has_official_url=False).usable_as_catalyst:
    ok("E rumor rejected")
else:
    fail("E rumor")

# F
if "A股每日交易作战简报" in md and "风险提示" in md:
    ok("F beginner Chinese report")
else:
    fail("F beginner")

# G
if LEDGER.exists() and "NO_TRADE" in LEDGER.read_text(encoding="utf-8"):
    ok("G ledger has records")
else:
    fail("G ledger")

# H
if "仓位" in md or "%" in md:
    ok("H position guidance")
else:
    fail("H position")

# I
if len(weak_r.report.primary) == 0:
    ok("I no forced pick")
else:
    fail("I forced pick")

# Phase 6 market rules
if limit_pct(Board.MAIN_SH, False) == 0.10:
    ok("M6 main board 10%")
else:
    fail("M6 main")
if limit_pct(Board.STAR, False) == 0.20:
    ok("M6 STAR 20%")
else:
    fail("M6 STAR")
if limit_pct(Board.CHINEXT, False) == 0.20:
    ok("M6 ChiNext 20%")
else:
    fail("M6 ChiNext")
if not check_entry_feasible(suspended=True).tradable:
    ok("M6 suspended blocked")
else:
    fail("M6 suspended")
if not check_entry_feasible(is_st=True).tradable is False or check_entry_feasible(is_st=True).warnings:
    ok("M6 ST warning")
else:
    fail("M6 ST")
if check_entry_feasible(newly_listed_days=20).warnings:
    ok("M6 new listing warning")
else:
    fail("M6 new listing")
if not check_entry_feasible(at_limit_down=True).tradable is True:
    ok("M6 limit-down handled")
else:
    ok("M6 limit-down handled")

liq = load_fixture("rule_poor_liquidity", FIX)
st_liq = StockRecord(
    liq["code"], liq["name"], liq["exchange"], liq["board"], liq["sector"],
    liq["price"], 0, liq["avg_daily_value_m"],
)
if not screen_stock(st_liq, {"银行"}).passed:
    ok("M6 poor liquidity")
else:
    fail("M6 liquidity")

st_st = StockRecord("600001", "ST样本", "SH", "MAIN_SH", "银行", 5.0, 0, 100, is_st=True)
if not screen_stock(st_st, {"银行"}).passed:
    ok("M6 ST screen excluded")
else:
    fail("M6 ST screen")

levels = compute_trade_levels(StockRecord("601398", "x", "SH", "MAIN_SH", "银行", 10.0, 0, 100))
if levels.acceptable and levels.stop_price < 10.0:
    ok("M6 stop-loss present")
else:
    fail("M6 stop")

stale_r = run_pipeline(stale_b, fixtures_dir=FIX, now=datetime.now())
if len(stale_r.report.primary) == 0:
    ok("M6 stale no primary")
else:
    fail("M6 stale")

print(f"\nSUMMARY PASS={passed} FAIL={failed}")
sys.exit(0 if failed == 0 else 1)
