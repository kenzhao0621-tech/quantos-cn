"""Ensemble: baseline + ML ranker + risk adjustment with auto-fallback."""

from __future__ import annotations

from typing import Any


def rank_normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    syms = list(scores.keys())
    order = sorted(syms, key=lambda s: scores[s])
    n = len(order)
    return {s: (order.index(s) + 1) / n for s in syms}


def ensemble_score(
    baseline: dict[str, float],
    ml: dict[str, float] | None,
    risk_adj: dict[str, float] | None,
    *,
    ml_passed: bool,
    w_ml: float = 0.45,
    w_base: float = 0.35,
    w_risk: float = 0.20,
) -> dict[str, float]:
    """Final alpha score per symbol. Degrades to baseline-only if ML not validated."""
    b = rank_normalize(baseline)
    if not ml or not ml_passed:
        return {s: b.get(s, 0.5) for s in baseline}
    m = rank_normalize(ml)
    r = rank_normalize(risk_adj or baseline)
    syms = set(baseline) | set(m) | set(r)
    out: dict[str, float] = {}
    for s in syms:
        out[s] = w_ml * m.get(s, 0.5) + w_base * b.get(s, 0.5) + w_risk * r.get(s, 0.5)
    return out


def validation_gate(metrics: dict[str, Any] | None = None) -> bool:
    """Gate from upgrade spec — ML must pass or fallback to baseline-only."""
    from quant.models.ml_scorer import get_ml_gate_status

    if metrics is None:
        return bool(get_ml_gate_status().get("passed"))
    if metrics.get("no_future_leakage_tests") is False:
        return False
    ric = metrics.get("rank_ic_oos") or metrics.get("rank_ic") or {}
    if float(ric.get("mean_rank_ic") or 0) < 0.015:
        return False
    if float(ric.get("icir") or 0) < 0.20:
        return False
    if metrics.get("train", {}).get("trained") is False:
        return False
    if not metrics.get("cost_adjusted_return_positive", True):
        return False
    return True
