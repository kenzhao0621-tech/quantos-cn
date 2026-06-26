"""Walk-forward validation orchestration."""

from __future__ import annotations

import statistics
from typing import Any

from quant.validation.overfitting import walk_forward_splits
from quant.validation.rank_ic import daily_rank_ic, summarize_rank_ic


def run_walk_forward_validation(
    dates: list[str],
    daily_scores: dict[str, dict[str, float]],
    daily_forward_returns: dict[str, dict[str, float]],
    *,
    train_months: int = 36,
    test_months: int = 6,
    step_months: int = 6,
) -> dict[str, Any]:
    """Rolling train/test windows; compute Rank IC on each test segment."""
    if len(dates) < 60:
        return {"status": "INSUFFICIENT_DATES", "n_dates": len(dates)}

    splits = walk_forward_splits(
        dates,
        train_size=max(40, train_months * 21),
        test_size=max(10, test_months * 21),
        step=max(10, step_months * 21),
    )
    fold_results: list[dict[str, Any]] = []
    all_ics: list[float | None] = []

    for i, split in enumerate(splits):
        test_dates = [d for d in dates if split["test_start"] <= d <= split["test_end"]]
        fold_ics: list[float | None] = []
        for d in test_dates:
            scores = daily_scores.get(d, {})
            rets = daily_forward_returns.get(d, {})
            ic = daily_rank_ic(scores, rets)
            fold_ics.append(ic)
            all_ics.append(ic)
        summary = summarize_rank_ic(fold_ics)
        fold_results.append({
            "fold": i + 1,
            "train": f"{split['train_start']}..{split['train_end']}",
            "test": f"{split['test_start']}..{split['test_end']}",
            **summary,
        })

    overall = summarize_rank_ic(all_ics)
    passed = (
        overall.get("status") == "OK"
        and overall.get("mean_rank_ic", 0) >= 0.015
        and overall.get("icir", 0) >= 0.20
    )
    return {
        "status": "OK" if fold_results else "NO_SPLITS",
        "n_folds": len(fold_results),
        "folds": fold_results,
        "overall": overall,
        "walk_forward_passed": passed,
        "thresholds": {"rank_ic_mean_min": 0.015, "rank_ic_ir_min": 0.20},
    }
