"""Market regime classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MarketRegime(str, Enum):
    STRONG_BULL = "strong bullish trend"
    WEAK_BULL = "weak bullish trend"
    RANGE = "range-bound market"
    HIGH_VOL_RANGE = "high-volatility range"
    WEAK_BEAR = "weak bearish trend"
    STRONG_BEAR = "strong bearish trend"
    EVENT_DRIVEN = "event-driven market"
    INSUFFICIENT = "insufficient data"


@dataclass
class RegimeResult:
    regime: MarketRegime
    max_primary_candidates: int
    default_confidence_cap: str  # HIGH, MEDIUM, LOW, NO TRADE
    guidance_zh: str


def classify_regime(
    index_change_pct: Optional[float],
    advance_count: Optional[int] = None,
    decline_count: Optional[int] = None,
    volume_ratio: Optional[float] = None,
) -> RegimeResult:
    if index_change_pct is None:
        return RegimeResult(
            MarketRegime.INSUFFICIENT,
            0,
            "NO TRADE",
            "数据不足，今日建议观望。",
        )

    breadth = None
    if advance_count is not None and decline_count is not None:
        total = advance_count + decline_count
        breadth = advance_count / total if total else 0.5

    if index_change_pct <= -2.0 or (breadth is not None and breadth < 0.35):
        return RegimeResult(
            MarketRegime.STRONG_BEAR,
            0,
            "NO TRADE",
            "市场偏弱，默认不建议新开仓，以保存资金为先。",
        )
    if index_change_pct <= -0.8:
        return RegimeResult(
            MarketRegime.WEAK_BEAR,
            1,
            "LOW",
            "弱势环境，仅观察极个别强势结构，小仓试探。",
        )
    if abs(index_change_pct) < 0.5 and (volume_ratio or 1.0) < 1.1:
        return RegimeResult(
            MarketRegime.RANGE,
            2,
            "MEDIUM",
            "震荡市，减少标的数量，缩短持有周期，止损要 tighter。",
        )
    if index_change_pct >= 1.5 and (breadth is None or breadth >= 0.55):
        return RegimeResult(
            MarketRegime.STRONG_BULL,
            3,
            "HIGH",
            "趋势偏强，可跟踪主线板块，但仍需止损。",
        )
    if index_change_pct >= 0.3:
        return RegimeResult(
            MarketRegime.WEAK_BULL,
            2,
            "MEDIUM",
            "温和偏强，精选板块龙头，避免追高。",
        )
    return RegimeResult(
        MarketRegime.HIGH_VOL_RANGE,
        1,
        "LOW",
        "波动较大，优先观察，控制仓位。",
    )
