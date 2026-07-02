"""ValidationOS gate — §9.3 pass thresholds for the candidate advice pool.

A strategy that fails any hard requirement gets BLOCKED_BY_VALIDATION and must
never be presented as a recommendation. Insufficient history is itself a block.
"""

from __future__ import annotations

from typing import Any

DEFAULT_THRESHOLDS = {
    "min_oos_sharpe": 0.8,
    "max_drawdown_pct": -15.0,
    "min_days": 40,
    "require_benchmark_outperformance": True,
}


def evaluate_validation_gate(
    *,
    metrics: dict[str, Any],
    benchmark_return_pct: float | None,
    costs_included: bool,
    a_share_constraints_applied: bool,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    reasons: list[str] = []

    ret = metrics.get("return") or {}
    risk = metrics.get("risk") or {}
    n_days = int(metrics.get("n_days") or 0)

    if not costs_included:
        reasons.append("BLOCKED: transaction costs not included")
    if not a_share_constraints_applied:
        reasons.append("BLOCKED: A-share T+1/limit/suspension constraints not applied")
    if n_days < th["min_days"]:
        reasons.append(f"BLOCKED: insufficient_history ({n_days} < {th['min_days']} days)")
    if benchmark_return_pct is None:
        if th["require_benchmark_outperformance"]:
            reasons.append("BLOCKED: no real benchmark comparison")
    else:
        strat = float(ret.get("annualized_return_pct") or ret.get("cumulative_return_pct") or 0)
        if strat <= benchmark_return_pct:
            reasons.append(
                f"BLOCKED: does not beat benchmark ({strat:.2f}% <= {benchmark_return_pct:.2f}%)"
            )
    sharpe = float(risk.get("sharpe") or 0)
    if sharpe < th["min_oos_sharpe"]:
        reasons.append(f"BLOCKED: sharpe {sharpe:.2f} < {th['min_oos_sharpe']}")
    mdd = float(risk.get("max_drawdown_pct") or 0)
    if mdd < th["max_drawdown_pct"]:
        reasons.append(f"BLOCKED: max_drawdown {mdd:.2f}% breaches {th['max_drawdown_pct']}%")

    passed = not reasons
    return {
        "passed": passed,
        "verdict": "CANDIDATE_POOL_ELIGIBLE" if passed else "BLOCKED_BY_VALIDATION",
        "reasons": reasons,
        "thresholds": th,
        "disclaimer": "通过验证不代表未来盈利；仅供研究与辅助决策，不构成投资建议。",
    }
