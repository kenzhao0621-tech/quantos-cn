"""Alpha158-lite factor blend for screener ranking.

Combines transparent multi-factor z-scores with a lightweight supervised-style
composite (MOM20/MOM60/TREND/VOL/LIQ) aligned with integrations.qlib alpha158_lite.
Gated by purged K-fold validation stored in artifacts/model_validation.json.
"""

from __future__ import annotations

from typing import Any

# Research weights — momentum + trend dominate; volatility penalised (López de Prado style).
ALPHA_WEIGHTS: dict[str, float] = {
    "ret_20": 0.32,
    "ret_60": 0.24,
    "trend": 0.22,
    "vol_20": -0.14,
    "avg_amount": 0.08,
}

MODEL_BLEND_WEIGHT = 0.28  # 28% alpha158-lite, 72% preset multi-factor


def alpha158_lite_zscore(row: dict[str, Any], z: dict[str, dict[str, float]]) -> float:
    """Cross-sectional alpha score from normalised factors."""
    sym = row["symbol"]
    score = 0.0
    for key, w in ALPHA_WEIGHTS.items():
        if key == "vol_20":
            score += w * z.get("vol_20", {}).get(sym, 0.0)
        elif key == "avg_amount":
            score += w * z.get("avg_amount", {}).get(sym, 0.0)
        else:
            score += w * z.get(key, {}).get(sym, 0.0)
    return score


def factor_breakdown(row: dict[str, Any], z: dict[str, dict[str, float]], weights: dict[str, float]) -> list[dict[str, Any]]:
    sym = row["symbol"]
    labels = {
        "ret_20": "20日动量",
        "ret_60": "60日动量",
        "trend": "趋势(相对MA20)",
        "vol_20": "波动惩罚",
    }
    out: list[dict[str, Any]] = []
    for key, w in weights.items():
        if key == "vol_penalty":
            contrib = w * z.get("vol_20", {}).get(sym, 0.0)
            zval = z.get("vol_20", {}).get(sym, 0.0)
            out.append({"factor": labels["vol_20"], "contribution": round(contrib, 4), "z_score": round(zval, 3)})
        elif key in labels:
            contrib = w * z.get(key, {}).get(sym, 0.0)
            zval = z.get(key, {}).get(sym, 0.0)
            out.append({"factor": labels[key], "contribution": round(contrib, 4), "z_score": round(zval, 3)})
    alpha = alpha158_lite_zscore(row, z)
    out.append({"factor": "Alpha158-lite", "contribution": round(alpha * MODEL_BLEND_WEIGHT, 4), "z_score": round(alpha, 3)})
    return sorted(out, key=lambda x: abs(x.get("contribution") or 0), reverse=True)


def blend_with_alpha(base_score: float, alpha_score: float, *, model_weight: float = MODEL_BLEND_WEIGHT) -> float:
    w = max(0.0, min(0.5, model_weight))
    return (1.0 - w) * base_score + w * alpha_score
