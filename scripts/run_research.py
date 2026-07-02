#!/usr/bin/env python
"""Phase 5 ResearchOS runner — baselines vs parameter search on real data.

Usage:
    python scripts/run_research.py --mode quick --trials 30

Outputs artifacts/research/research_<ts>.json with:
- baseline comparison (CSI300 buy&hold, MA crossover, momentum, reversal,
  equal-weight liquidity top-k)
- random search best/blocked configs, parameter sensitivity, real-variant PBO
All windows are real data windows; degraded states are labeled.
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
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--max-symbols", type=int, default=200)
    args = parser.parse_args()

    from quant.research.panel import load_research_panel
    from quant.research.search import run_random_search
    from quant.research.strategies import (
        equal_weight_topk_liquidity,
        index_buy_hold_daily,
        ma_crossover_strategy,
        momentum_rank_strategy,
    )
    from quant.validation.performance import full_metrics

    panel = load_research_panel(max_symbols=args.max_symbols)
    if not panel.get("ok"):
        print(json.dumps(panel, ensure_ascii=False))
        return 2

    print(f"panel: {len(panel['symbols'])} symbols, window {panel['window']['start']}..{panel['window']['end']} ({panel['window']['days']} days)")

    hs300_daily, hs300_meta = index_buy_hold_daily(
        start=panel["window"]["start"], end=panel["window"]["end"],
    )
    baselines = {
        "hs300_buy_hold": {**(full_metrics(hs300_daily, label="hs300_buy_hold") if hs300_daily else {"status": "DEGRADED"}), "benchmark_window": hs300_meta.get("window") or hs300_meta},
        "momentum_20_top10": full_metrics(momentum_rank_strategy(panel, window=20, top_k=10), label="momentum_20_top10"),
        "momentum_60_top10": full_metrics(momentum_rank_strategy(panel, window=60, top_k=10), label="momentum_60_top10"),
        "mean_reversion_10_top10": full_metrics(momentum_rank_strategy(panel, window=10, top_k=10, reverse=True), label="mean_reversion_10_top10"),
        "ma_crossover_5_20": full_metrics(ma_crossover_strategy(panel, fast=5, slow=20, top_k=10), label="ma_crossover_5_20"),
        "equal_weight_liquid_top50": full_metrics(equal_weight_topk_liquidity(panel, top_k=50), label="equal_weight_liquid_top50"),
    }
    bench_ann = None
    if baselines["hs300_buy_hold"].get("status") == "OK":
        bench_ann = baselines["hs300_buy_hold"]["return"]["annualized_return_pct"]

    search = run_random_search(panel, n_trials=args.trials, benchmark_return_pct=bench_ann)

    report = {
        "mode": args.mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "panel_window": panel["window"],
        "universe": {"n_symbols": len(panel["symbols"]), "selection": "top mean_amount, main boards"},
        "benchmark_annualized_return_pct": bench_ann,
        "baselines": baselines,
        "search": search,
        "disclaimer": "历史研究结果，不代表未来收益；仅供研究与辅助决策，不构成投资建议。",
    }
    out_dir = ROOT / "artifacts" / "research"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nbaselines (sharpe / ann.return% / mdd%):")
    for name, m in baselines.items():
        if m.get("status") == "OK":
            print(f"  {name}: {m['risk']['sharpe']} / {m['return']['annualized_return_pct']} / {m['risk']['max_drawdown_pct']}")
        else:
            print(f"  {name}: {m.get('status')}")
    best = search.get("best_eligible") or search.get("best")
    if best:
        print(f"\nbest {'ELIGIBLE' if search.get('best_eligible') else '(not eligible)'}: {best['params']} sharpe={best['metrics']['risk']['sharpe']}")
    print(f"eligible={search['eligible_count']} blocked={search['blocked_count']} pbo={search.get('pbo_real_variants')}")
    print(f"report: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
