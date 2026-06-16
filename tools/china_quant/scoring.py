"""Transparent 100-point scoring model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScoreBreakdown:
    market_regime_fit: float = 0.0
    sector_strength: float = 0.0
    trend_momentum: float = 0.0
    volume_liquidity: float = 0.0
    fundamental_quality: float = 0.0
    valuation_context: float = 0.0
    confirmed_catalysts: float = 0.0
    risk_control: float = 0.0
    deductions: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        raw = (
            self.market_regime_fit
            + self.sector_strength
            + self.trend_momentum
            + self.volume_liquidity
            + self.fundamental_quality
            + self.valuation_context
            + self.confirmed_catalysts
            + self.risk_control
            - self.deductions
        )
        return max(0.0, min(100.0, raw))

    def tier(self) -> str:
        t = self.total
        if t >= 75:
            return "primary"
        if t >= 65:
            return "watchlist"
        return "below_threshold"


def score_candidate(
    *,
    regime_fit: float,
    sector_strength: float,
    trend_momentum: float,
    volume_liquidity: float,
    fundamental_quality: float,
    valuation_context: float,
    confirmed_catalysts: float,
    risk_control: float,
    overheated: bool = False,
    weak_liquidity: bool = False,
    unverified_rumor: bool = False,
    poor_rr: bool = False,
) -> ScoreBreakdown:
    sb = ScoreBreakdown(
        market_regime_fit=min(15, regime_fit),
        sector_strength=min(15, sector_strength),
        trend_momentum=min(20, trend_momentum),
        volume_liquidity=min(10, volume_liquidity),
        fundamental_quality=min(15, fundamental_quality),
        valuation_context=min(10, valuation_context),
        confirmed_catalysts=min(10, confirmed_catalysts),
        risk_control=min(5, risk_control),
    )
    if overheated:
        sb.deductions += 10
        sb.notes.append("价格过热")
    if weak_liquidity:
        sb.deductions += 8
        sb.notes.append("流动性偏弱")
    if unverified_rumor:
        sb.deductions += 15
        sb.notes.append("未证实传闻")
    if poor_rr:
        sb.deductions += 10
        sb.notes.append("盈亏比不佳")
    return sb
