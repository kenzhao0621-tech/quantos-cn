#!/usr/bin/env python
"""KronosOS smoke test.

Usage:
    python scripts/run_kronos_smoke.py --symbol 000001.SZ --horizon 5 --model mini

Prints the distribution forecast and normalized signal; writes
artifacts/reports/kronos_smoke_<ts>.json. Exit 0 even when degraded —
degradation is a labeled, legitimate state; exit 1 only on hard errors.
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
    parser.add_argument("--symbol", default="000001.SZ")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--model", default="mini", choices=["mini", "small"])
    parser.add_argument("--n-paths", type=int, default=10)
    args = parser.parse_args()

    from quant.models.kronos import KronosSignalProvider

    provider = KronosSignalProvider(model=f"kronos-{args.model}", n_paths=args.n_paths)
    pred = provider.predict_distribution(args.symbol, horizon=args.horizon)
    signal = provider.generate_signal(pred)

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "prediction": {k: v for k, v in pred.items() if k != "paths"},
        "n_paths": len(pred.get("paths") or []),
        "signal": signal,
    }
    out_dir = ROOT / "artifacts" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"kronos_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps({**out, "paths_sample": (pred.get("paths") or [])[:3]},
                               ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"report: {path.relative_to(ROOT)}")
    if pred.get("degraded"):
        print(f"NOTE: degraded — {pred.get('reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
