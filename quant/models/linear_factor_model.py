"""Linear factor model — interpretable fallback when Ranker unavailable."""

from __future__ import annotations

from typing import Any

from quant.models.baseline import DEFAULT_BASELINE_WEIGHTS, score_baseline


def predict_linear_batch(
    symbols: list[str],
    z_layers: dict[str, dict[str, dict[str, float]]],
    *,
    weights: dict[str, float] | None = None,
    layer: str = "size_industry",
) -> dict[str, float]:
    w = weights or DEFAULT_BASELINE_WEIGHTS
    return {sym: score_baseline(z_layers, sym, weights=w, layer=layer) for sym in symbols}


def rank_normalize_linear(scores: dict[str, float]) -> dict[str, float]:
    from quant.models.ensemble import rank_normalize

    return rank_normalize(scores)
