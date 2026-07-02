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


def annualized_return(daily_returns_pct: list[float]) -> float:
    if not daily_returns_pct:
        return 0.0
    cum = cumulative_return(daily_returns_pct) / 100.0
    years = len(daily_returns_pct) / TRADING_DAYS_PER_YEAR
    if years <= 0 or cum <= -1:
        return 0.0
    return round(((1.0 + cum) ** (1.0 / years) - 1.0) * 100.0, 3)


def annualized_volatility(daily_returns_pct: list[float]) -> float:
    if len(daily_returns_pct) < 2:
        return 0.0
    return round(statistics.pstdev([r / 100.0 for r in daily_returns_pct]) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100.0, 3)


def downside_deviation(daily_returns_pct: list[float]) -> float:
    downside = [r / 100.0 for r in daily_returns_pct if r < 0]
    if len(downside) < 2:
        return 0.0
    return round(statistics.pstdev(downside) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100.0, 3)


def tail_loss_95(daily_returns_pct: list[float]) -> float:
    """Empirical 5th percentile daily return (VaR95, pct)."""
    if not daily_returns_pct:
        return 0.0
    s = sorted(daily_returns_pct)
    idx = max(0, int(len(s) * 0.05) - 1)
    return round(s[idx], 3)


def profit_factor(daily_returns_pct: list[float]) -> float:
    gains = sum(r for r in daily_returns_pct if r > 0)
    losses = abs(sum(r for r in daily_returns_pct if r < 0))
    if losses < 1e-9:
        return 0.0 if gains < 1e-9 else 99.0
    return round(gains / losses, 3)


def bootstrap_ci(daily_returns_pct: list[float], *, n_boot: int = 500, seed: int = 42) -> dict[str, float]:
    """Bootstrap 90% CI on the mean daily return (pct)."""
    if len(daily_returns_pct) < 10:
        return {"low": 0.0, "high": 0.0, "n_boot": 0}
    import random

    rng = random.Random(seed)
    means = []
    n = len(daily_returns_pct)
    for _ in range(n_boot):
        sample = [daily_returns_pct[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(sample))
    means.sort()
    return {
        "low": round(means[int(n_boot * 0.05)], 4),
        "high": round(means[int(n_boot * 0.95)], 4),
        "n_boot": n_boot,
    }


def full_metrics(daily_net_pct: list[float], *, label: str = "strategy") -> dict[str, Any]:
    """Complete §9.2 metric block from real daily net returns."""
    if not daily_net_pct:
        return {"label": label, "status": "INSUFFICIENT_SAMPLE"}
    gains = [r for r in daily_net_pct if r > 0]
    losses = [r for r in daily_net_pct if r < 0]
    return {
        "label": label,
        "status": "OK",
        "n_days": len(daily_net_pct),
        "return": {
            "cumulative_return_pct": round(cumulative_return(daily_net_pct), 3),
            "annualized_return_pct": annualized_return(daily_net_pct),
            "win_rate_pct": round(len(gains) / len(daily_net_pct) * 100, 1),
            "profit_factor": profit_factor(daily_net_pct),
            "average_gain_pct": round(statistics.fmean(gains), 3) if gains else 0.0,
            "average_loss_pct": round(statistics.fmean(losses), 3) if losses else 0.0,
        },
        "risk": {
            "max_drawdown_pct": max_drawdown(daily_net_pct),
            "annualized_volatility_pct": annualized_volatility(daily_net_pct),
            "sharpe": sharpe_ratio(daily_net_pct),
            "sortino": sortino_ratio(daily_net_pct),
            "calmar": round(annualized_return(daily_net_pct) / abs(max_drawdown(daily_net_pct)), 3)
            if max_drawdown(daily_net_pct) < -0.01 else 0.0,
            "downside_deviation_pct": downside_deviation(daily_net_pct),
            "tail_loss_95_pct": tail_loss_95(daily_net_pct),
            "worst_day_pct": round(min(daily_net_pct), 3),
        },
        "robustness": {
            "bootstrap_ci_mean_daily_pct": bootstrap_ci(daily_net_pct),
        },
    }


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
