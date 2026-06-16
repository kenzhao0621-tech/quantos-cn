#!/usr/bin/env python3
"""Run production verification and next-trading-day research."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant.next_session_research import run_deterministic_suites, run_research, write_reports


def main() -> int:
    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not run_id:
        print("Usage: run-next-session-research.py RUN_ID", file=sys.stderr)
        return 2

    # Re-verify ledger duplicate protection
    subprocess.run(
        [sys.executable, "-m", "quant", "run-daily", "--mode", "latest-available", "--run-id", run_id],
        cwd=ROOT,
        capture_output=True,
    )

    test_results = run_deterministic_suites()
    decision = run_research(run_id, skip_tests=True)
    paths = write_reports(decision, test_results)

    summary = {
        "system_readiness": decision.decision,
        "run_id": decision.run_id,
        "data_date": decision.data_date,
        "target_trading_date": decision.target_trading_date,
        "selected_provider": decision.spot_provider,
        "row_count": decision.row_count,
        "quality_result": decision.quality_status,
        "market_regime": decision.market_regime,
        "candidate_decision": decision.decision,
        "candidate": decision.candidate,
        "ledger_append": decision.ledger_result,
        "limitations": decision.limitations,
        "reports": {k: str(v) for k, v in paths.items()},
        "tests": test_results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
