#!/usr/bin/env python3
"""Build Alpha158-compatible wide feature cache."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    p = argparse.ArgumentParser(description="Build Alpha158 wide parquet cache")
    p.add_argument("--mode", choices=["sample", "full"], default="sample")
    p.add_argument("--sample-size", type=int, default=300)
    p.add_argument("--lookback-days", type=int, default=800)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    from quant.features.alpha158_cache import build_alpha158_cache

    manifest = build_alpha158_cache(
        mode=args.mode,
        sample_size=args.sample_size,
        lookback_days=args.lookback_days,
        force=args.force,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest.get("built") else 1


if __name__ == "__main__":
    raise SystemExit(main())
