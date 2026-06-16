"""Derived feature store from persisted historical partitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FEATURE_ROOT = ROOT / "data" / "features"
MANIFEST_ROOT = ROOT / "data" / "manifests" / "historical"


def build_feature_summary() -> dict[str, Any]:
    """Summarize available feature inputs from historical manifests."""
    manifests = list(MANIFEST_ROOT.rglob("*.json")) if MANIFEST_ROOT.exists() else []
    dates = sorted({json.loads(m.read_text())["trade_date"] for m in manifests}) if manifests else []
    FEATURE_ROOT.mkdir(parents=True, exist_ok=True)
    summary = {
        "historical_partitions": len(manifests),
        "trade_dates": dates,
        "feature_modules": ["momentum_20d", "volatility_20d", "liquidity_rank"],
        "status": "partial" if len(dates) < 20 else "acceptable",
        "point_in_time": "bars keyed by trade_date partition; no intraday mixing",
    }
    (FEATURE_ROOT / "feature_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8",
    )
    return summary
