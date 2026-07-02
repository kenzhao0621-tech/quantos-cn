"""Confidence formula (v2.2 §6.6) — fixed weights, banded interpretation."""

from __future__ import annotations

from typing import Any, Dict, Optional

CONFIDENCE_WEIGHTS: Dict[str, float] = {
    "signal_agreement": 0.30,
    "data_freshness": 0.25,
    "historical_validation_strength": 0.20,
    "regime_clarity": 0.15,
    "model_stability": 0.10,
}

BANDS = [
    (0.40, "low", "低，不建议执行"),
    (0.60, "watch", "观察，等待更好价格或更多确认"),
    (0.75, "medium", "中等，可以轻仓执行"),
    (0.85, "high", "较高，可以按计划执行，但仍需止损"),
    (1.01, "exceptional", "极少出现，必须解释原因，不能滥用"),
]


def compute_confidence(inputs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Inputs are 0-1 per component; missing components score 0 (never inflated)."""
    inputs = inputs or {}
    components = {}
    acc = 0.0
    missing = []
    for name, w in CONFIDENCE_WEIGHTS.items():
        raw = inputs.get(name)
        if raw is None:
            missing.append(name)
            val = 0.0
        else:
            val = min(1.0, max(0.0, float(raw)))
        components[name] = {"weight": w, "value": round(val, 3)}
        acc += w * val
    confidence = round(min(1.0, max(0.0, acc)), 3)
    band_key, band_label = "low", BANDS[0][2]
    for threshold, key, label in BANDS:
        if confidence < threshold:
            band_key, band_label = key, label
            break
    return {
        "confidence": confidence,
        "band": band_key,
        "band_label_zh": band_label,
        "components": components,
        "missing_components": missing,
        "actionable": confidence >= 0.60,
    }
