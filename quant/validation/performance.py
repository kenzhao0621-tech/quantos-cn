"""Canonical performance engine — gross/net returns, drawdown, Sharpe, Sortino, Calmar."""

from __future__ import annotations

import math
import statistics
from typing import Any

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_DAILY = 0.02 / TRADING_DAYS_PER_YEAR


def cumulative_return(daily_returns_pct: list[float]) -> float:
    """Geometric cumulative return from daily percent returns."""
    if not daily_returns_pct:
        return 0.0
    prod = 1.0
    for r in daily_returns_pct:
        prod *= 1.0 + r / 100.0
    return (prod - 1.0) * 100.0


def max_drawdown(daily_returns_pct: list[float]) -> float:
    if not daily_returns_pct:
        return 0.0
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in daily_returns_pct:
        equity *= 1.0 + r / 100.0
        peak = max(peak, equity)
        dd = (equity / peak - 1.0) * 100.0
        max_dd = min(max_dd, dd)
    return round(max_dd, 3)


def sharpe_ratio(daily_returns_pct: list[float], *, annualize: bool = True) -> float:
    if len(daily_returns_pct) < 2:
        return 0.0
    excess = [r / 100.0 - RISK_FREE_DAILY for r in daily_returns_pct]
    std = statistics.pstdev(excess)
    if std < 1e-12:
        return 0.0
    sr = statistics.fmean(excess) / std
    return round(sr * math.sqrt(TRADING_DAYS_PER_YEAR) if annualize else sr, 4)


def sortino_ratio(daily_returns_pct: list[float]) -> float:
    if len(daily_returns_pct) < 2:
        return 0.0
    excess = [r / 100.0 - RISK_FREE_DAILY for r in daily_returns_pct]
    downside = [x for x in excess if x < 0]
    if not downside:
        return round(sharpe_ratio(daily_returns_pct), 4)
    dd_std = statistics.pstdev(downside)
    if dd_std < 1e-12:
        return 0.0
    return round(statistics.fmean(excess) / dd_std * math.sqrt(TRADING_DAYS_PER_YEAR), 4)


def summarize_performance(
    daily_gross_pct: list[float],
    daily_net_pct: list[float],
    *,
    label: str = "portfolio",
    cost_profile: str = "research",
) -> dict[str, Any]:
    if not daily_net_pct:
        return {"label": label, "status": "INSUFFICIENT_SAMPLE", "n_days": 0}
    gross_cum = cumulative_return(daily_gross_pct or daily_net_pct)
    net_cum = cumulative_return(daily_net_pct)
    mdd = max_drawdown(daily_net_pct)
    sr = sharpe_ratio(daily_net_pct)
    so = sortino_ratio(daily_net_pct)
    calmar = round(net_cum / abs(mdd), 4) if mdd < -0.01 else 0.0
    return {
        "label": label,
        "status": "OK",
        "n_days": len(daily_net_pct),
        "gross_cumulative_return_pct": round(gross_cum, 3),
        "net_cumulative_return_pct": round(net_cum, 3),
        "avg_daily_net_return_pct": round(statistics.fmean(daily_net_pct), 3),
        "max_drawdown_pct": mdd,
        "sharpe": sr,
        "sortino": so,
        "calmar": calmar,
        "cost_profile": cost_profile,
        "formula_version": "perf_v1",
    }
