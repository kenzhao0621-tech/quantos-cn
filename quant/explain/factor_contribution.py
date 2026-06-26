"""ExplainabilityOS — factor contribution decomposition."""

from __future__ import annotations

from typing import Any


def explain_candidate(row: dict[str, Any], *, validation_status: dict[str, Any] | None = None) -> dict[str, Any]:
    """Structured explanation — no 'AI thinks it will rise'."""
    breakdown = row.get("factor_breakdown") or []
    factor_contrib = [
        {"factor": b.get("factor"), "contribution": b.get("contribution"), "direction": b.get("direction")}
        for b in breakdown
        if isinstance(b, dict)
    ]
    val = validation_status or {}
    return {
        "symbol": row.get("symbol"),
        "final_score": row.get("score"),
        "baseline_score": row.get("baseline_score"),
        "ensemble_score": row.get("ensemble_score"),
        "ml_score": row.get("ml_score"),
        "factor_contribution": factor_contrib,
        "industry_contribution": row.get("sector"),
        "event_contribution": row.get("disclosure_flag") or None,
        "risk_penalty": row.get("vol_20"),
        "cost_penalty": row.get("estimated_round_trip_cost_cny"),
        "liquidity_status": "OK" if float(row.get("avg_amount") or 0) >= 5e7 else "LOW",
        "historical_rankic_evidence": val.get("verdict"),
        "not_trade_reason": (row.get("tradability") or {}).get("blockers"),
        "forbidden_phrases": ["保证收益", "稳赚", "AI确定会涨", "无风险"],
    }
