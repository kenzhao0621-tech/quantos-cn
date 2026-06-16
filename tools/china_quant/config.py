"""Configurable thresholds and regime parameters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoringConfig:
    primary_threshold: float = 78.0
    watchlist_threshold: float = 68.0
    regime_fit_max: float = 10.0
    sector_max: float = 15.0
    trend_max: float = 15.0
    price_volume_max: float = 10.0
    liquidity_max: float = 10.0
    fundamental_max: float = 15.0
    valuation_max: float = 10.0
    policy_catalyst_max: float = 5.0
    institutional_max: float = 5.0
    risk_max: float = 5.0


@dataclass
class RiskConfig:
    min_rr_strong_bull: float = 1.8
    min_rr_range: float = 2.0
    min_rr_weak: float = 2.5
    max_position_pct: float = 15.0
    max_portfolio_heat: float = 40.0
    stamp_duty_sell: float = 0.0005  # 2023-08-28 reduced rate
    commission: float = 0.00025
    slippage_bps: float = 5.0


REGIME_THRESHOLDS = {
    "strong bullish trend": 75.0,
    "weak bullish trend": 78.0,
    "range-bound market": 80.0,
    "high-volatility range": 82.0,
    "weak bearish trend": 85.0,
    "strong bearish trend": 999.0,
}

DEFAULT_CONFIG = ScoringConfig()
DEFAULT_RISK = RiskConfig()
