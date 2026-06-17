"""True cross-sectional Rank IC — Spearman(predicted rank, realized forward return)."""

from __future__ import annotations

import math
import statistics
from typing import Any


def _spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 3:
        return None
    n = len(x)
    rx = _rank(x)
    ry = _rank(y)
    mx = statistics.fmean(rx)
    my = statistics.fmean(ry)
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den_x = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    den_y = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    if den_x < 1e-12 or den_y < 1e-12:
        return None
    return num / (den_x * den_y)


def _rank(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def daily_rank_ic(
    predicted_scores: dict[str, float],
    realized_returns: dict[str, float],
) -> float | None:
    """Spearman IC for one date cross-section."""
    symbols = [s for s in predicted_scores if s in realized_returns]
    if len(symbols) < 5:
        return None
    x = [predicted_scores[s] for s in symbols]
    y = [realized_returns[s] for s in symbols]
    return _spearman(x, y)


def summarize_rank_ic(daily_ics: list[float | None]) -> dict[str, Any]:
    vals = [v for v in daily_ics if v is not None]
    if len(vals) < 5:
        return {
            "status": "INSUFFICIENT_SAMPLE",
            "n_days": len(vals),
            "min_days_required": 20,
        }
    mean_ic = statistics.fmean(vals)
    std_ic = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    icir = mean_ic / std_ic if std_ic > 1e-9 else 0.0
    pos_ratio = sum(1 for v in vals if v > 0) / len(vals)
    t_stat = mean_ic / (std_ic / math.sqrt(len(vals))) if std_ic > 1e-9 else 0.0
    return {
        "status": "OK",
        "n_days": len(vals),
        "mean_rank_ic": round(mean_ic, 4),
        "rank_ic_std": round(std_ic, 4),
        "icir": round(icir, 4),
        "positive_ic_ratio": round(pos_ratio, 4),
        "t_statistic": round(t_stat, 3),
        "definition": "Spearman(predicted_score, realized_forward_return) per signal date",
    }
