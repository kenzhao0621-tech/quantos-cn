"""PortfolioOS constraint defaults — Spec §7.3."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioConstraints:
    max_single_weight: float = 0.05
    max_industry_weight: float = 0.15
    max_daily_turnover: float = 0.20
    min_avg_amount_cny: float = 5e7
    st_forbidden: bool = True
    suspended_forbidden: bool = True
    limit_up_buy_forbidden: bool = True


DEFAULT_CONSTRAINTS = PortfolioConstraints()
