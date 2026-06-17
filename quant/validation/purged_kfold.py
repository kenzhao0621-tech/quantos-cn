"""Purged K-Fold cross-validation for time-series factor strategies (López de Prado).

Embargo/purge gaps prevent label leakage when signals use overlapping return windows.
"""

from __future__ import annotations

import statistics
from typing import Any


def purged_kfold_splits(
    dates: list[str],
    *,
    n_splits: int = 5,
    train_size: int = 40,
    test_size: int = 5,
    purge_days: int = 5,
    embargo_days: int = 2,
) -> list[dict[str, Any]]:
    """Generate purged train/test index ranges on sorted trade dates."""
    n = len(dates)
    if n < train_size + test_size + purge_days + embargo_days + 2:
        return []
    splits: list[dict[str, Any]] = []
    step = max(1, (n - train_size - test_size - purge_days) // max(n_splits, 1))
    for k in range(n_splits):
        train_end_idx = train_size + k * step - 1
        if train_end_idx + purge_days + test_size + embargo_days >= n:
            break
        test_start_idx = train_end_idx + purge_days + 1
        test_end_idx = min(test_start_idx + test_size - 1, n - 1)
        embargo_end_idx = min(test_end_idx + embargo_days, n - 1)
        splits.append({
            "fold": k + 1,
            "train_start": dates[0],
            "train_end": dates[train_end_idx],
            "purge_gap_days": purge_days,
            "test_start": dates[test_start_idx],
            "test_end": dates[test_end_idx],
            "embargo_end": dates[embargo_end_idx],
        })
    return splits


def evaluate_screener_purged_kfold(
    *,
    fold_returns: list[float],
    fold_hit_rates: list[float],
    n_trials: int = 1,
) -> dict[str, Any]:
    """Summarise OOS fold performance for gating screener output."""
    if not fold_returns:
        return {"passed": False, "reason": "no_oos_folds", "folds": 0}
    mean_ret = statistics.fmean(fold_returns)
    std_ret = statistics.pstdev(fold_returns) if len(fold_returns) > 1 else 0.0
    hit = statistics.fmean(fold_hit_rates) if fold_hit_rates else 0.0
    sharpe_like = (mean_ret / std_ret) if std_ret > 1e-9 else 0.0
    passed = mean_ret > 0 and hit >= 0.45 and sharpe_like > 0.2
    return {
        "passed": passed,
        "folds": len(fold_returns),
        "mean_oos_return_pct": round(mean_ret, 3),
        "std_oos_return_pct": round(std_ret, 3),
        "mean_hit_rate": round(hit, 3),
        "sharpe_like": round(sharpe_like, 3),
        "n_trials": n_trials,
        "method": "purged_kfold_embargo",
        "reference": "López de Prado — Advances in Financial Machine Learning (2018)",
    }
