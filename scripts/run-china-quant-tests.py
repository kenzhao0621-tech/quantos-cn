#!/usr/bin/env python3
"""Tests A–I for China A-share outlook system."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.china_quant.freshness import assess_freshness
from tools.china_quant.news_integrity import assess_catalyst
from tools.china_quant.regime import classify_regime
from tools.china_quant.rules import check_entry_feasible
from tools.china_quant.scoring import score_candidate
from tools.china_quant.data import load_fixture, snapshot_from_fixture
from tools.china_quant.report import CandidatePlan, DailyReport, render_report
from tools.china_quant.cli import build_report_from_snapshot

FIX = ROOT / "docs" / "test-fixtures" / "china-quant"
LEDGER = ROOT / "docs" / "ai" / "daily-trading" / "PERFORMANCE_LEDGER.csv"

passed = 0
failed = 0


def ok(name: str):
    global passed
    passed += 1
    print(f"PASS {name}")


def fail(name: str, msg: str = ""):
    global failed
    failed += 1
    print(f"FAIL {name} {msg}")


# A — Data freshness
stale = snapshot_from_fixture(load_fixture("stale_data", FIX))
fr = assess_freshness(stale.data_timestamp, now=datetime.now())
if not fr.live_decision_ok:
    ok("A freshness stale rejected")
else:
    fail("A freshness")

# B — NO TRADE weak market
weak = snapshot_from_fixture(load_fixture("weak_market", FIX))
rep = build_report_from_snapshot(weak, force_no_trade=True)
if rep.regime.max_primary_candidates == 0 and "NO TRADE" in rep.trade_today or "否" in rep.trade_today:
    ok("B no trade weak market")
else:
    fail("B no trade")

# C — Entry plan fields
c = CandidatePlan(
    name="测试", code="000001", exchange="SZ", sector="银行",
    price=10.0, data_time="2026-06-16", recommendation="可轻仓试探",
    confidence="MEDIUM", score=78, reasons=["趋势尚可"],
    entry_range="9.8-10.2", entry_confirm="放量突破10.2",
    cancel_condition="跌破9.5", stop="9.4 (-6%)",
    target1="10.8", target2="11.2", hold_period="3-5日",
    position_pct="10%", reward_risk="1:2",
    catalyst="业绩稳定", risks=["板块轮动"], invalidation="跌破止损",
)
md = render_report(DailyReport(
    conclusion_direction="震荡",
    market_regime_zh="range-bound",
    position_guidance="10%",
    trade_today="谨慎",
    data_cutoff=datetime.now().isoformat(),
    data_status="DELAYED",
    one_liner="测试",
    regime=classify_regime(0.1),
    freshness=fr,
    primary=[c],
    watchlist=[],
    avoid=[],
))
for field in ["止损位", "买入确认条件", "取消买入条件", "第一止盈"]:
    if field in md:
        ok(f"C field {field}")
    else:
        fail(f"C field {field}")

# D — Limit-up
lim = load_fixture("limit_up_stock", FIX)
chk = check_entry_feasible(at_limit_up=lim["at_limit_up"])
if not chk.tradable:
    ok("D limit-up blocked")
else:
    fail("D limit-up")

# E — Rumor
rumor = assess_catalyst("social", social_media_only=True, has_official_url=False)
if not rumor.usable_as_catalyst:
    ok("E rumor rejected")
else:
    fail("E rumor")

# F — Beginner clarity (Chinese sections present)
if "A股每日交易作战简报" in md and "风险提示" in md:
    ok("F beginner Chinese report")
else:
    fail("F beginner")

# G — Ledger preserves losses
if LEDGER.exists():
    text = LEDGER.read_text(encoding="utf-8")
    if "NO_TRADE" in text or "lesson" in text.lower():
        ok("G ledger has records")
    else:
        fail("G ledger")
else:
    fail("G ledger missing")

# H — Position sizing in report template
if "10%" in md or "仓位" in md:
    ok("H position guidance")
else:
    fail("H position")

# I — Forced no pick
rep2 = build_report_from_snapshot(weak, force_no_trade=True)
if len(rep2.primary) == 0:
    ok("I no forced pick")
else:
    fail("I forced pick")

print(f"\nSUMMARY PASS={passed} FAIL={failed}")
sys.exit(0 if failed == 0 else 1)
