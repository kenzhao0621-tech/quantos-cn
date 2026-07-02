#!/usr/bin/env python
"""Phase 4 quick backtest — real bars, real benchmark, full §9.2 metrics, §9.3 gate.

Usage:
    python scripts/run_backtest.py --mode quick [--preset balanced] [--top-n 5] [--lookback 60]

Writes artifacts/backtests/backtest_<ts>.json. Always prints the REAL date window.
Exit 0 = ran (result may still be BLOCKED_BY_VALIDATION — that is a valid honest outcome);
exit 2 = blocked by data.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["quick", "standard"], default="quick")
    parser.add_argument("--preset", default="balanced")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--lookback", type=int, default=60)
    parser.add_argument("--universe", default="all_liquid", help="informational label")
    parser.add_argument("--from", dest="from_date", default=None, help="informational; window is data-driven")
    args = parser.parse_args()

    from gateway.backtest.screener_backtest import run_screener_portfolio_backtest

    lookback = args.lookback if args.mode == "quick" else max(args.lookback, 120)
    result = run_screener_portfolio_backtest(
        preset=args.preset, lookback_days=lookback, top_n=args.top_n,
    )

    if result.get("status") == "BLOCKED_BY_DATA":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    # Gate is computed inside run_screener_portfolio_backtest (§9.3).
    gate = result.get("validation_gate", {"verdict": "GATE_MISSING", "reasons": []})
    m = result.get("metrics", {})
    benchmarks = result.get("benchmarks", {})
    result["mode"] = args.mode
    result["generated_at"] = datetime.now().isoformat(timespec="seconds")

    out_dir = ROOT / "artifacts" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    win = result.get("window", {})
    print(f"status={result.get('status')} gate={gate['verdict']}")
    print(f"REAL window: {win.get('start')} .. {win.get('end')} ({win.get('days')} signal days)")
    print(f"metrics: sharpe={m.get('sharpe')} total={m.get('total_return_pct')}% mdd={m.get('max_drawdown_pct')}%")
    print(f"benchmarks: {json.dumps(benchmarks, ensure_ascii=False)[:300]}")
    if gate["reasons"]:
        for r in gate["reasons"]:
            print(f"  {r}")
    print(f"report: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
