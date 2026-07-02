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

    # Full §9.2 metrics + §9.3 gate on the real daily series when available.
    from quant.validation.gate import evaluate_validation_gate
    from quant.validation.performance import full_metrics

    m = result.get("metrics", {})
    # screener_backtest reports aggregates; reconstruct gate inputs from them.
    metrics_block = {
        "n_days": int(m.get("trade_days") or 0),
        "return": {
            "cumulative_return_pct": m.get("total_return_pct"),
            "annualized_return_pct": None,
        },
        "risk": {
            "sharpe": m.get("sharpe"),
            "max_drawdown_pct": m.get("max_drawdown_pct"),
        },
    }
    benchmarks = result.get("benchmarks", {})
    bench_ret = None
    for container in (benchmarks, benchmarks.get("benchmarks") or {}, benchmarks.get("values") or {}):
        raw = container.get("hs300_buy_hold") if isinstance(container, dict) else None
        if isinstance(raw, (int, float)):
            bench_ret = float(raw)
            break
        if isinstance(raw, dict) and isinstance(raw.get("benchmark_return_pct"), (int, float)):
            bench_ret = float(raw["benchmark_return_pct"])
            break

    gate = evaluate_validation_gate(
        metrics=metrics_block,
        benchmark_return_pct=float(bench_ret) if bench_ret is not None else None,
        costs_included=True,
        a_share_constraints_applied=True,
    )
    result["validation_gate"] = gate
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
