"""ResearchOS random parameter search with sensitivity + honest blocking.

Optuna is optional; when unavailable we fall back to seeded random search and
label the method. Every trial runs on real panel data with costs; results
failing the §9.3 gate are recorded as blocked configs, not hidden.
"""

from __future__ import annotations

import random
from typing import Any

PARAM_SPACE = {
    "window": [5, 10, 20, 40, 60],
    "top_k": [5, 10, 20],
    "vol_penalty": [0.0, 0.5, 1.0],
    "reverse": [False, True],  # momentum vs mean-reversion
}


def _sample_params(rng: random.Random) -> dict[str, Any]:
    return {k: rng.choice(v) for k, v in PARAM_SPACE.items()}


def run_random_search(panel: dict[str, Any], *, n_trials: int = 30, seed: int = 42,
                      benchmark_return_pct: float | None = None) -> dict[str, Any]:
    from quant.research.strategies import momentum_rank_strategy
    from quant.validation.gate import evaluate_validation_gate
    from quant.validation.performance import full_metrics

    rng = random.Random(seed)
    seen: set = set()
    trials: list[dict[str, Any]] = []
    for t in range(n_trials):
        params = _sample_params(rng)
        key = tuple(sorted(params.items()))
        if key in seen:
            continue
        seen.add(key)
        daily = momentum_rank_strategy(panel, **params)
        metrics = full_metrics(daily, label=f"trial_{t}")
        gate = evaluate_validation_gate(
            metrics=metrics, benchmark_return_pct=benchmark_return_pct,
            costs_included=True, a_share_constraints_applied=True,
        )
        trials.append({
            "trial": t,
            "params": params,
            "n_days": metrics.get("n_days", 0),
            "metrics": metrics if metrics.get("status") == "OK" else {"status": metrics.get("status")},
            "gate": {"verdict": gate["verdict"], "reasons": gate["reasons"]},
            "daily_returns": daily,
        })

    scored = [t for t in trials if t["metrics"].get("status") == "OK"]
    scored.sort(key=lambda t: t["metrics"]["risk"]["sharpe"], reverse=True)
    eligible = [t for t in scored if t["gate"]["verdict"] == "CANDIDATE_POOL_ELIGIBLE"]
    blocked = [t for t in trials if t["gate"]["verdict"] != "CANDIDATE_POOL_ELIGIBLE"]

    # PBO over真实 trial variants (replaces the same-series permutation approximation).
    pbo = None
    series = [t["daily_returns"] for t in scored[:12] if len(t["daily_returns"]) >= 20]
    if len(series) >= 3:
        min_len = min(len(s) for s in series)
        from quant.validation.overfitting import probability_backtest_overfitting

        pbo = probability_backtest_overfitting([s[-min_len:] for s in series])

    return {
        "method": "random_search",
        "n_trials_requested": n_trials,
        "n_trials_run": len(trials),
        "best": _strip(scored[0]) if scored else None,
        "best_eligible": _strip(eligible[0]) if eligible else None,
        "eligible_count": len(eligible),
        "blocked_count": len(blocked),
        "blocked_examples": [_strip(b) for b in blocked[:5]],
        "sensitivity": parameter_sensitivity(scored),
        "pbo_real_variants": pbo,
        "all_trials": [_strip(t) for t in trials],
    }


def _strip(trial: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in trial.items() if k != "daily_returns"}


def parameter_sensitivity(scored_trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean sharpe per parameter value — how fragile is the result?"""
    import statistics

    out: dict[str, Any] = {}
    for param in PARAM_SPACE:
        buckets: dict[str, list[float]] = {}
        for t in scored_trials:
            val = str(t["params"].get(param))
            sharpe = t["metrics"]["risk"]["sharpe"]
            buckets.setdefault(val, []).append(sharpe)
        out[param] = {
            v: {"mean_sharpe": round(statistics.fmean(s), 3), "n": len(s)}
            for v, s in sorted(buckets.items())
        }
    return out
