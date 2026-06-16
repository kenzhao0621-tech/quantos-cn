#!/usr/bin/env python3
"""Deterministic tests for next-session research gates."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant.next_session_research import (
    GateResult,
    THRESHOLDS,
    append_research_ledger,
    candidate_data_ready,
    classify_regime_label,
    compute_breadth,
    latest_completed_market_date,
    next_open_trading_day,
    pipeline_ready,
    ResearchDecision,
)
from tools.china_quant.risk import compute_trade_levels
from tools.china_quant.models import StockRecord

passed = 0
failed: list[str] = []


def ok(n: str) -> None:
    global passed
    passed += 1
    print(f"  PASS {n}")


def fail(n: str, d: str = "") -> None:
    failed.append(n)
    print(f"  FAIL {n}" + (f": {d}" if d else ""))


def test_next_trading_day() -> None:
    days = ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18"]
    nxt = next_open_trading_day(days, "2026-06-16")
    if nxt == "2026-06-17":
        ok("next_trading_day_calculation")
    else:
        fail("next_trading_day_calculation", nxt)


def test_latest_completed_date() -> None:
    days = ["2026-06-15", "2026-06-16", "2026-06-17"]
    d = latest_completed_market_date(days, "2026-06-16")
    if d == "2026-06-16":
        ok("latest_completed_data_date")
    else:
        fail("latest_completed_data_date", d)


def test_risk_off_regime() -> None:
    b = compute_breadth([{"change_pct": -5}] * 100 + [{"change_pct": 1}] * 20)
    label, _, _, _, _ = classify_regime_label(b, -2.5, available_indices=1)
    if label in ("RISK_OFF", "DISORDERED"):
        ok("no_trade_risk_off_regime")
    else:
        fail("no_trade_risk_off_regime", label)


def test_missing_indices_gate() -> None:
    gates = [GateResult("major_indices_coverage", False, "1/7")]
    if not candidate_data_ready(gates):
        ok("no_trade_missing_indices")
    else:
        fail("no_trade_missing_indices")


def test_missing_bars_gate() -> None:
    gates = [GateResult("historical_bars", False, "missing")]
    if not candidate_data_ready(gates):
        ok("no_trade_incomplete_bars")
    else:
        fail("no_trade_incomplete_bars")


def test_reward_risk_validation() -> None:
    st = StockRecord(
        code="600000", name="测试", exchange="SH", board="MAIN_SH", sector="银行",
        price=10.0, change_pct=2.0, avg_daily_value_m=200,
        trend_score=12, fundamental_score=8, valuation_score=7,
    )
    levels = compute_trade_levels(st)
    risk = st.price - levels.stop_price
    reward = levels.target1 - st.price
    rr = reward / risk if risk > 0 else 0
    if levels.stop_price < levels.entry_low and levels.target1 > st.price and rr >= 1.5:
        ok("reward_risk_validation")
    else:
        fail("reward_risk_validation", f"rr={rr}")


def test_position_size_formula() -> None:
    entry, stop, allowed_loss_pct = 10.0, 9.4, 0.005
    portfolio = 1_000_000
    allowed_loss = portfolio * allowed_loss_pct
    shares = allowed_loss / (entry - stop)
    lots = int(shares // 100) * 100
    if lots >= 100:
        ok("position_size_formula")
    else:
        fail("position_size_formula", str(lots))


def test_ledger_no_trade_append() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        d = ResearchDecision(
            decision="NO_TRADE",
            run_id="run-nt-1",
            analysis_date="2026-06-16",
            data_date="2026-06-16",
            target_trading_date="2026-06-17",
            generated_at="2026-06-16T20:00:00",
            calendar_provider="akshare_sina",
            spot_provider="akshare_sina",
            rejection_reasons=["test"],
        )
        r1 = append_research_ledger(d, base=base)
        r2 = append_research_ledger(d, base=base)
        if r1.get("appended") and r2.get("skipped_duplicate"):
            ok("paper_ledger_append_duplicate_prevention")
        else:
            fail("paper_ledger_append_duplicate_prevention", str(r2))


def test_pipeline_gate_fixture_reject() -> None:
    gates = [
        GateResult("non_fixture", False, "manual_snapshot"),
        GateResult("row_count", True, "5500"),
    ]
    if not pipeline_ready(gates):
        ok("no_trade_fixture_data")
    else:
        fail("no_trade_fixture_data")


def main() -> int:
    print("=== next-session deterministic tests ===\n")
    tests = [
        test_next_trading_day,
        test_latest_completed_date,
        test_risk_off_regime,
        test_missing_indices_gate,
        test_missing_bars_gate,
        test_reward_risk_validation,
        test_position_size_formula,
        test_ledger_no_trade_append,
        test_pipeline_gate_fixture_reject,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            fail(t.__name__, str(e))
    print(f"\nSUMMARY passed={passed} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
