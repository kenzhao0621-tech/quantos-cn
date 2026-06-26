"""Transparent baseline model with industry-neutral factors."""

from __future__ import annotations

from typing import Any

# Configurable weights — not hardcoded in UI
DEFAULT_BASELINE_WEIGHTS: dict[str, float] = {
    "ret_20": 0.18,
    "ret_60": 0.14,
    "trend": 0.10,
    "vol_20": -0.14,
    "avg_amount": 0.10,
    "value_score": 0.12,
    "quality_score": 0.12,
    "growth_score": 0.08,
    "industry_relative_mom_20": 0.06,
}


def score_baseline(
    z_layers: dict[str, dict[str, dict[str, float]]],
    symbol: str,
    *,
    weights: dict[str, float] | None = None,
    risk_event: float = 0.0,
    layer: str = "size_industry",
) -> float:
    """Score from neutralized z-scores. Uses size_industry layer by default."""
    w = weights or DEFAULT_BASELINE_WEIGHTS
    z = z_layers.get(layer, z_layers.get("industry", {}))
    total = risk_event
    key_map = {
        "ret_20": "ret_20",
        "ret_60": "ret_60",
        "trend": "trend",
        "vol_20": "vol_20",
        "avg_amount": "avg_amount",
        "value_score": "value_score",
        "quality_score": "quality_score",
        "growth_score": "growth_score",
        "industry_relative_mom_20": "industry_relative_mom_20",
    }
    for factor, weight in w.items():
        fk = key_map.get(factor, factor)
        if fk in z and symbol in z[fk]:
            total += weight * z[fk][symbol]
    return total


def score_row_baseline(row: dict[str, Any], z_industry: dict[str, dict[str, float]], weights: dict[str, float] | None = None) -> float:
    sym = row["symbol"]
    w = weights or DEFAULT_BASELINE_WEIGHTS
    s = float(row.get("risk_event_score") or 0)
    for key, weight in w.items():
        if key in z_industry and sym in z_industry[key]:
            s += weight * z_industry[key][sym]
    return s
