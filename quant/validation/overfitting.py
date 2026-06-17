"""Backtest overfitting metrics — DSR, PBO, walk-forward helpers.

DSR output semantics (Bailey & López de Prado, simplified):
  - dsr_statistic: (SR - E[max SR]) / std(SR) — z-like deflated statistic
  - dsr_probability: P(true SR > 0 | multiple testing) via Normal CDF
  - passed: dsr_probability > 0.95 AND dsr_statistic > 0

PBO requires >= 8 candidate return series with >= 20 observations each.
Otherwise returns PBO_STATUS = INSUFFICIENT_SAMPLE.
"""

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
    """Deflated Sharpe with explicit output types for UI and gates."""
    if n_obs < 10 or n_trials < 1:
        return {
            "status": "INSUFFICIENT_SAMPLE",
            "dsr_statistic": None,
            "dsr_probability": None,
            "sharpe_observed": round(sharpe, 4),
            "n_trials": n_trials,
            "n_obs": n_obs,
            "passed": False,
            "reason": "need_n_obs>=10",
        }
    sr_var = (
        1 + 0.5 * sharpe ** 2 - skew * sharpe + (kurtosis - 3) / 4 * sharpe ** 2
    ) / max(n_obs - 1, 1)
    sr_std = math.sqrt(max(sr_var, 1e-12))
    euler = 0.5772156649
    z1 = statistics.NormalDist().inv_cdf(1 - 1 / n_trials)
    z2 = statistics.NormalDist().inv_cdf(1 - 1 / n_trials * math.e)
    max_sr = sr_std * ((1 - euler) * z1 + euler * z2)
    dsr_stat = (sharpe - max_sr) / sr_std if sr_std > 0 else 0.0
    dsr_prob = statistics.NormalDist().cdf(dsr_stat)
    return {
        "status": "OK",
        "dsr_statistic": round(dsr_stat, 4),
        "dsr_probability": round(dsr_prob, 4),
        "sharpe_observed": round(sharpe, 4),
        "expected_max_sharpe": round(max_sr, 4),
        "n_trials": n_trials,
        "n_obs": n_obs,
        "passed": dsr_stat > 0 and dsr_prob > 0.95,
        "output_type": "dsr_statistic + dsr_probability",
        "threshold": "dsr_probability > 0.95",
    }


def probability_backtest_overfitting(
    returns_matrix: list[list[float]],
    *,
    min_strategies: int = 8,
    min_obs: int = 20,
) -> dict[str, Any]:
    """CSCV-style PBO proxy. Requires multiple candidate strategies."""
    n_strategies = len(returns_matrix)
    if n_strategies < min_strategies:
        return {
            "status": "INSUFFICIENT_SAMPLE",
            "pbo": None,
            "passed": False,
            "reason": f"need>={min_strategies}_strategies_got_{n_strategies}",
            "n_strategies": n_strategies,
        }
    n = len(returns_matrix[0]) if returns_matrix else 0
    if n < min_obs:
        return {
            "status": "INSUFFICIENT_SAMPLE",
            "pbo": None,
            "passed": False,
            "reason": f"need>={min_obs}_obs_got_{n}",
            "n_strategies": n_strategies,
        }
    half = n // 2
    if half < 5:
        return {"status": "INSUFFICIENT_SAMPLE", "pbo": None, "passed": False, "reason": "split_too_short"}
    is_rets = [sum(row[:half]) for row in returns_matrix]
    oos_rets = [sum(row[half:]) for row in returns_matrix]
    best_is = max(range(len(is_rets)), key=lambda i: is_rets[i])
    oos_rank = sorted(oos_rets, reverse=True).index(oos_rets[best_is]) + 1
    pbo = oos_rank / len(oos_rets)
    return {
        "status": "OK",
        "pbo": round(pbo, 4),
        "passed": pbo < 0.5,
        "best_is_idx": best_is,
        "oos_rank": oos_rank,
        "n_strategies": n_strategies,
        "n_obs": n,
        "method": "half_split_rank_proxy",
    }


def build_pbo_candidate_matrix(
    primary_returns: list[float],
    *,
    n_variants: int = 12,
) -> list[list[float]]:
    """Build candidate matrix from primary series via lag/scale perturbations for PBO."""
    if len(primary_returns) < 20:
        return [primary_returns] if primary_returns else []
    matrix: list[list[float]] = []
    for lag in range(min(4, n_variants)):
        shifted = [0.0] * lag + primary_returns[:-lag] if lag else list(primary_returns)
        matrix.append(shifted)
    for scale in (0.5, 0.75, 1.25, 1.5, 2.0):
        matrix.append([r * scale for r in primary_returns])
    for step in (2, 3):
        matrix.append(primary_returns[::step] + primary_returns[1::step][: len(primary_returns) // 2])
    return matrix[:n_variants]


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
