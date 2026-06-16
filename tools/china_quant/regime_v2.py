"""Enhanced market regime from real index and breadth data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from tools.china_quant.config import REGIME_THRESHOLDS
from tools.china_quant.regime import MarketRegime, RegimeResult, classify_regime


@dataclass
class RegimeAnalysis:
    result: RegimeResult
    evidence: list[str] = field(default_factory=list)
    confidence: str = "MEDIUM"
    invalidation: str = ""
    exposure_ceiling: str = "20%"
    min_score_threshold: float = 78.0
    allowed_setups: list[str] = field(default_factory=list)


def classify_regime_v2(
    indices: dict[str, Any],
    spot_rows: list[dict],
    *,
    index_hist: Optional[list[dict]] = None,
) -> RegimeAnalysis:
    sh = indices.get("sh", {})
    chg = sh.get("change_pct", 0)
    advance = sum(1 for r in spot_rows if r.get("change_pct", 0) > 0)
    decline = sum(1 for r in spot_rows if r.get("change_pct", 0) < 0)
    limit_up = sum(1 for r in spot_rows if r.get("change_pct", 0) >= 9.5)
    limit_down = sum(1 for r in spot_rows if r.get("change_pct", 0) <= -9.5)

    base = classify_regime(chg, advance, decline)
    evidence = [
        f"上证指数涨跌幅: {chg:+.2f}%",
        f"上涨家数: {advance}, 下跌家数: {decline}",
        f"涨停约: {limit_up}, 跌停约: {limit_down}",
    ]

    if index_hist and len(index_hist) >= 20:
        closes = [float(b.get("close", b.get("收盘", 0))) for b in index_hist[-20:]]
        ma20 = sum(closes) / len(closes)
        evidence.append(f"指数 vs MA20: {'上方' if closes[-1] > ma20 else '下方'}")

    regime_name = base.regime.value
    min_score = REGIME_THRESHOLDS.get(regime_name, 78.0)
    exposure = {"strong bullish trend": "30%", "weak bullish trend": "20%", "range-bound market": "15%"}.get(regime_name, "5%")
    if base.max_primary_candidates == 0:
        exposure = "0%"

    confidence = "HIGH" if abs(chg) > 1.0 and advance + decline > 100 else "MEDIUM"
    if base.regime == MarketRegime.INSUFFICIENT:
        confidence = "LOW"

    return RegimeAnalysis(
        result=base,
        evidence=evidence,
        confidence=confidence,
        invalidation="指数单日跌超2%或广度恶化至35%以下",
        exposure_ceiling=exposure,
        min_score_threshold=min_score,
        allowed_setups=["趋势延续", "板块龙头回调"] if base.max_primary_candidates > 0 else [],
    )
