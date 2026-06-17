"""Backtest overfitting metrics — DSR, PBO, walk-forward helpers."""

from __future__ import annotations

import math
import statistics
from typing import Any


def deflated_sharpe_ratio(
    sharpe: float,
    n_trials: int,
    *,
    n_obs: int = 252,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> dict[str, Any]:
    """Bailey & López de Prado deflated Sharpe (simplified)."""
    if n_obs < 2 or n_trials < 1:
        return {"dsr": 0.0, "passed": False, "reason": "insufficient_observations"}
    sr_var = (1 + 0.5 * sharpe ** 2 - skew * sharpe + (kurtosis - 3) / 4 * sharpe ** 2) / max(n_obs - 1, 1)
    sr_std = math.sqrt(max(sr_var, 1e-12))
    euler = 0.5772156649
    max_sr = sr_std * ((1 - euler) * statistics.NormalDist().inv_cdf(1 - 1 / n_trials) + euler * statistics.NormalDist().inv_cdf(1 - 1 / n_trials * math.e))
    dsr = (sharpe - max_sr) / sr_std if sr_std > 0 else 0.0
    return {
        "dsr": round(dsr, 4),
        "sharpe": round(sharpe, 4),
        "n_trials": n_trials,
        "n_obs": n_obs,
        "passed": dsr > 0,
    }


def probability_backtest_overfitting(
    returns_matrix: list[list[float]],
    *,
    n_permutations: int = 200,
) -> dict[str, Any]:
    """Simplified PBO via in-sample vs out-of-sample rank (Lopez de Prado style)."""
    if not returns_matrix or len(returns_matrix) < 2:
        return {"pbo": 1.0, "passed": False, "reason": "need_multiple_splits"}
    n = len(returns_matrix[0])
    if n < 4:
        return {"pbo": 1.0, "passed": False, "reason": "short_window"}
    half = n // 2
    is_rets = [sum(row[:half]) for row in returns_matrix]
    oos_rets = [sum(row[half:]) for row in returns_matrix]
    best_is = max(range(len(is_rets)), key=lambda i: is_rets[i])
    oos_rank = sorted(oos_rets, reverse=True).index(oos_rets[best_is]) + 1
    pbo = oos_rank / len(oos_rets)
    return {
        "pbo": round(pbo, 4),
        "passed": pbo < 0.5,
        "best_is_idx": best_is,
        "oos_rank": oos_rank,
        "n_strategies": len(returns_matrix),
    }


def walk_forward_splits(dates: list[str], *, train_size: int, test_size: int, step: int) -> list[dict[str, Any]]:
    splits: list[dict[str, Any]] = []
    i = 0
    while i + train_size + test_size <= len(dates):
        splits.append({
            "train_start": dates[i],
            "train_end": dates[i + train_size - 1],
            "test_start": dates[i + train_size],
            "test_end": dates[i + train_size + test_size - 1],
        })
        i += step
    return splits


def benchmark_comparison(strategy_return_pct: float, benchmarks: dict[str, float]) -> dict[str, Any]:
    beats = {k: strategy_return_pct > v for k, v in benchmarks.items()}
    return {
        "strategy_return_pct": round(strategy_return_pct, 3),
        "benchmarks": {k: round(v, 3) for k, v in benchmarks.items()},
        "beats": beats,
        "beat_count": sum(1 for x in beats.values() if x),
    }
