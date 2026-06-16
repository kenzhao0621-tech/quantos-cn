"""Multi-factor scoring model v2 — spec §13."""

from __future__ import annotations

from dataclasses import dataclass, field

from tools.china_quant.config import DEFAULT_CONFIG, REGIME_THRESHOLDS, ScoringConfig
from tools.china_quant.models import StockRecord


@dataclass
class FactorScore:
    regime_fit: float = 0.0
    sector_rotation: float = 0.0
    trend_momentum: float = 0.0
    price_volume: float = 0.0
    liquidity: float = 0.0
    fundamentals: float = 0.0
    valuation: float = 0.0
    policy_catalyst: float = 0.0
    institutional: float = 0.0
    risk_control: float = 0.0
    deductions: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        raw = (
            self.regime_fit + self.sector_rotation + self.trend_momentum
            + self.price_volume + self.liquidity + self.fundamentals
            + self.valuation + self.policy_catalyst + self.institutional
            + self.risk_control - self.deductions
        )
        return max(0.0, min(100.0, raw))

    def tier(self, regime_name: str, cfg: ScoringConfig = DEFAULT_CONFIG) -> str:
        thresh = REGIME_THRESHOLDS.get(regime_name, cfg.primary_threshold)
        if self.total >= thresh:
            return "primary"
        if self.total >= cfg.watchlist_threshold:
            return "watchlist"
        return "below_threshold"


def score_stock_v2(
    stock: StockRecord,
    *,
    regime_name: str,
    sector_strength: float,
    has_confirmed_catalyst: bool,
    institutional_score: float = 0.0,
    stale: bool = False,
    source_conflict: bool = False,
    cfg: ScoringConfig = DEFAULT_CONFIG,
) -> FactorScore:
    fs = FactorScore(
        regime_fit=min(cfg.regime_fit_max, 8 if "bear" in regime_name else 10),
        sector_rotation=min(cfg.sector_max, sector_strength),
        trend_momentum=min(cfg.trend_max, stock.trend_score),
        price_volume=min(cfg.price_volume_max, stock.trend_score * 0.5),
        liquidity=min(cfg.liquidity_max, 10 if stock.avg_daily_value_m >= 100 else 5),
        fundamentals=min(cfg.fundamental_max, stock.fundamental_score),
        valuation=min(cfg.valuation_max, stock.valuation_score),
        policy_catalyst=min(cfg.policy_catalyst_max, 5 if has_confirmed_catalyst else 0),
        institutional=min(cfg.institutional_max, institutional_score),
        risk_control=min(cfg.risk_max, 4),
    )
    if stock.change_pct > 9:
        fs.deductions += 12
        fs.notes.append("价格过度延伸")
    if stock.avg_daily_value_m < 50:
        fs.deductions += 10
        fs.notes.append("流动性偏弱")
    if stock.rumor_only_catalyst:
        fs.deductions += 15
        fs.notes.append("传闻催化")
    if stale:
        fs.deductions += 20
        fs.notes.append("数据陈旧")
    if source_conflict:
        fs.deductions += 10
        fs.notes.append("来源冲突")
    return fs
