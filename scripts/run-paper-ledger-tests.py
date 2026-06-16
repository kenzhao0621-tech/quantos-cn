#!/usr/bin/env python3
"""Deterministic tests for paper signal ledger integration."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant.paper_ledger import (
    DuplicateRunError,
    append_correction,
    append_daily_signals,
    find_records_by_run_id,
    load_signal_records,
    run_id_in_ledger,
    signal_ledger_path,
)
from tools.china_quant.daily_runner import DailyRunResult
from tools.china_quant.modes import OperatingMode
from tools.china_quant.report import CandidatePlan, DailyReport
from tools.china_quant.freshness import FreshnessResult, DataStatus
from tools.china_quant.regime import MarketRegime, RegimeResult

passed = 0
failed: list[str] = []


def ok(name: str) -> None:
    global passed
    passed += 1
    print(f"  PASS {name}")


def fail(name: str, detail: str = "") -> None:
    failed.append(name)
    print(f"  FAIL {name}" + (f": {detail}" if detail else ""))


def _minimal_report(*, primary: list[CandidatePlan]) -> DailyReport:
    regime = RegimeResult(MarketRegime.RANGE, 3, "MEDIUM", "震荡")
    fresh = FreshnessResult(DataStatus.DELAYED, True, "ok", None, __import__("datetime").datetime.now())
    return DailyReport(
        conclusion_direction="震荡",
        market_regime_zh="range",
        position_guidance="30%",
        trade_today="谨慎",
        data_cutoff="2026-06-16",
        data_status="DELAYED",
        one_liner="test",
        regime=regime,
        freshness=fresh,
        primary=primary,
        watchlist=[],
        avoid=[],
    )


def _candidate() -> CandidatePlan:
    return CandidatePlan(
        name="测试股份",
        code="600000",
        exchange="SH",
        sector="银行",
        price=10.5,
        data_time="test",
        recommendation="可轻仓试探",
        confidence="MEDIUM",
        score=82.0,
        reasons=["强动量"],
        entry_range="10.20-10.60",
        entry_confirm="放量突破",
        cancel_condition="跌破10.00",
        stop="9.80 (-3%)",
        target1="11.50",
        target2="12.00",
        hold_period="3-5日",
        position_pct="8%",
        reward_risk="2.1",
        catalyst="无",
        risks=["轮动"],
        invalidation="跌破9.80",
    )


def test_candidate_day_append() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        result = DailyRunResult(
            mode=OperatingMode.LATEST_AVAILABLE,
            analysis_date="2026-06-16",
            report=_minimal_report(primary=[_candidate()]),
            provider_status={"run_id": "run-cand-1", "spot": "akshare_sina"},
            limitations=["freshness=DELAYED"],
        )
        out = append_daily_signals(base, result, run_id="run-cand-1")
        recs = load_signal_records(base)
        if out.appended == 1 and recs[-1]["symbol"] == "600000" and recs[-1]["run_id"] == "run-cand-1":
            ok("candidate_day_append")
        else:
            fail("candidate_day_append", str(recs))


def test_zero_candidate_day_append() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        result = DailyRunResult(
            mode=OperatingMode.LATEST_AVAILABLE,
            analysis_date="2026-06-16",
            report=_minimal_report(primary=[]),
            provider_status={"run_id": "run-zero-1", "spot": "akshare_sina"},
            limitations=["freshness=DELAYED"],
        )
        out = append_daily_signals(base, result, run_id="run-zero-1")
        rec = load_signal_records(base)[0]
        if out.record_type == "zero_day" and rec["status"] == "zero_candidates" and rec["symbol"] == "NO_CANDIDATE":
            ok("zero_candidate_day_append")
        else:
            fail("zero_candidate_day_append", str(rec))


def test_duplicate_run_rejection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        result = DailyRunResult(
            mode=OperatingMode.LATEST_AVAILABLE,
            analysis_date="2026-06-16",
            report=_minimal_report(primary=[]),
            provider_status={"run_id": "run-dup-1"},
            limitations=[],
        )
        append_daily_signals(base, result, run_id="run-dup-1")
        try:
            append_daily_signals(base, result, run_id="run-dup-1")
            fail("duplicate_run_rejection", "expected DuplicateRunError")
        except DuplicateRunError:
            ok("duplicate_run_rejection")


def test_correction_linked_record() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        result = DailyRunResult(
            mode=OperatingMode.LATEST_AVAILABLE,
            analysis_date="2026-06-16",
            report=_minimal_report(primary=[_candidate()]),
            provider_status={"run_id": "run-corr-1", "spot": "tushare"},
            limitations=["freshness=END_OF_DAY"],
        )
        append_daily_signals(base, result, run_id="run-corr-1")
        original_id = load_signal_records(base)[0]["record_id"]
        corr = append_correction(
            base,
            run_id="run-corr-1",
            corrects_record_id=original_id,
            plan=_candidate(),
            provider="tushare",
            freshness="END_OF_DAY",
            market_data_date="2026-06-16",
            status="corrected_signal",
        )
        recs = load_signal_records(base)
        if len(recs) == 2 and recs[1]["record_type"] == "correction" and recs[1]["corrects_record_id"] == original_id:
            ok("correction_linked_record")
        else:
            fail("correction_linked_record", str(corr))


def test_no_mutation_of_historical_records() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        result = DailyRunResult(
            mode=OperatingMode.LATEST_AVAILABLE,
            analysis_date="2026-06-16",
            report=_minimal_report(primary=[_candidate()]),
            provider_status={"run_id": "run-immutable-1"},
            limitations=[],
        )
        append_daily_signals(base, result, run_id="run-immutable-1")
        before = signal_ledger_path(base).read_text(encoding="utf-8")
        original = json.loads(before.strip().splitlines()[0])
        append_correction(
            base,
            run_id="run-immutable-1",
            corrects_record_id=original["record_id"],
            plan=_candidate(),
            provider="akshare_sina",
            freshness="DELAYED",
            market_data_date="2026-06-16",
        )
        after_lines = signal_ledger_path(base).read_text(encoding="utf-8").splitlines()
        first_after = json.loads(after_lines[0])
        if first_after == original and len(after_lines) == 2:
            ok("no_mutation_of_historical_records")
        else:
            fail("no_mutation_of_historical_records")


def main() -> int:
    print("=== paper-ledger deterministic tests ===\n")
    for t in [
        test_candidate_day_append,
        test_zero_candidate_day_append,
        test_duplicate_run_rejection,
        test_correction_linked_record,
        test_no_mutation_of_historical_records,
    ]:
        try:
            t()
        except Exception as e:
            fail(t.__name__, str(e))
    print(f"\nSUMMARY passed={passed} failed={len(failed)}")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
