#!/usr/bin/env python
"""AgentsOS runner — full multi-agent research analysis for one symbol.

Usage:
    python scripts/run_agents_analysis.py --symbol 000001.SZ --date latest
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="000001.SZ")
    parser.add_argument("--date", default="latest")
    args = parser.parse_args()

    as_of = None if args.date in ("latest", "", None) else args.date
    from gateway.agents.quantos import run_agents_analysis

    result = run_agents_analysis(args.symbol, as_of_date=as_of)
    final = result["final"]
    print(f"symbol={result['symbol']} as_of={result['as_of_date']}")
    print(f"RATING: {final['rating']} — {final['rating_meaning']}")
    print(f"composite={final['score']} confidence={final['confidence']}")
    print("\n多空辩论：")
    for p in final["bull_case"][:4]:
        print(f"  [多] {p}")
    for p in final["bear_case"][:4]:
        print(f"  [空] {p}")
    if final["risks"]:
        print("风险：")
        for r in final["risks"]:
            print(f"  - {r}")
    print("失效条件：")
    for c in final["invalidation_conditions"]:
        print(f"  - {c}")
    if final["degraded_agents"]:
        print(f"降级 agent: {final['degraded_agents']}")
    print(f"\n{final['disclaimer']}")
    print(f"artifact: {result.get('artifact')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
