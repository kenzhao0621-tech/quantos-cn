"""Automatic factor selection via rolling Rank IC."""

from __future__ import annotations

import statistics
from typing import Any

from quant.validation.rank_ic import daily_rank_ic


def factor_rank_ic_series(
    daily_panels: list[dict[str, dict[str, float]]],
    daily_returns: list[dict[str, float]],
    factor_key: str,
) -> list[float | None]:
    """daily_panels[i][factor][symbol] vs forward returns."""
    ics: list[float | None] = []
    for panel, rets in zip(daily_panels, daily_returns):
        scores = panel.get(factor_key, {})
        ics.append(daily_rank_ic(scores, rets))
    return ics


def select_factors_by_rank_ic(
    factor_names: list[str],
    daily_panels: list[dict[str, dict[str, float]]],
    daily_returns: list[dict[str, float]],
    *,
    min_mean_ic: float = 0.005,
    min_ir: float = 0.15,
    max_factors: int = 12,
) -> dict[str, Any]:
    """Keep factors with positive mean Rank IC and IR above threshold."""
    ranked: list[dict[str, Any]] = []
    for name in factor_names:
        ics = [v for v in factor_rank_ic_series(daily_panels, daily_returns, name) if v is not None]
        if len(ics) < 10:
            continue
        mean_ic = statistics.fmean(ics)
        std_ic = statistics.pstdev(ics) or 1e-9
        ir = mean_ic / std_ic
        ranked.append({
            "factor": name,
            "mean_rank_ic": round(mean_ic, 4),
            "rank_ic_std": round(std_ic, 4),
            "icir": round(ir, 4),
            "n_days": len(ics),
            "selected": mean_ic >= min_mean_ic and ir >= min_ir,
        })
    ranked.sort(key=lambda x: x["icir"], reverse=True)
    selected = [r["factor"] for r in ranked if r["selected"]][:max_factors]
    return {
        "selected_factors": selected,
        "factor_rank_ic": ranked,
        "selection_rule": f"mean_ic>={min_mean_ic}, icir>={min_ir}",
    }
