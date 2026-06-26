"""Counterfactual Engine — event vs baseline move decomposition."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def estimate_counterfactual(
    *,
    event: str,
    observed_move: float,
    industry_baseline_move: float,
) -> dict[str, Any]:
    excess = observed_move - industry_baseline_move
    return {
        "event": event,
        "observed_move": round(observed_move, 4),
        "estimated_without_event": round(industry_baseline_move, 4),
        "causal_strength": round(excess, 4),
        "confidence": 0.35 if abs(excess) > 0.02 else 0.2,
        "evidence": "industry_baseline_residual",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "forbidden": ["guaranteed_return", "BUY", "SELL"],
    }
