"""End-to-end daily outlook pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from tools.china_quant.data import load_fixture
from tools.china_quant.freshness import DataStatus, assess_freshness
from tools.china_quant.models import MarketBundle, StockRecord, bundle_from_fixture
from tools.china_quant.news_integrity import assess_catalyst
from tools.china_quant.regime import RegimeResult, classify_regime
from tools.china_quant.report import CandidatePlan, DailyReport
from tools.china_quant.risk import compute_trade_levels
from tools.china_quant.scoring import score_candidate
from tools.china_quant.screening import filter_universe
from tools.china_quant.sectors import rank_sectors


@dataclass
class PipelineResult:
    report: DailyReport
    data_provenance: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


def _stock_to_plan(stock: StockRecord, score: float, levels, regime: RegimeResult) -> CandidatePlan:
    conf = regime.default_confidence_cap
    if score >= 80:
        conf = "HIGH"
    elif score >= 75:
        conf = "MEDIUM"
    rec = "可轻仓试探" if score >= 75 else "观察"
    catalyst = stock.official_catalyst or "无已确认公告催化（仅技术面/板块逻辑）"
    return CandidatePlan(
        name=stock.name,
        code=stock.code,
        exchange=stock.exchange,
        sector=stock.sector,
        price=stock.price,
        data_time="fixture",
        recommendation=rec,
        confidence=conf,
        score=score,
        reasons=[
            f"板块{stock.sector}处于强势名单",
            f"趋势评分{stock.trend_score:.0f}/20",
            "模型评分（非收益承诺）",
        ],
        entry_range=f"{levels.entry_low:.2f}-{levels.entry_high:.2f}",
        entry_confirm=levels.entry_confirm,
        cancel_condition=levels.cancel_condition,
        stop=f"{levels.stop_price:.2f} (-{levels.stop_pct:.0f}%)",
        target1=f"{levels.target1:.2f}",
        target2=f"{levels.target2:.2f}",
        hold_period=levels.hold_period,
        position_pct=levels.position_pct,
        reward_risk=levels.reward_risk,
        catalyst=catalyst,
        risks=["板块轮动", "大盘转弱", "流动性变化"],
        invalidation=f"收盘跌破止损 {levels.stop_price:.2f}",
    )


def run_pipeline(bundle: MarketBundle, *, fixtures_dir: Path, now: Optional[datetime] = None) -> PipelineResult:
    snap = bundle.snapshot
    fresh = assess_freshness(snap.data_timestamp, now=now)
    regime = classify_regime(snap.sh_index_change_pct, snap.advance_count, snap.decline_count)

    provenance = [
        f"价格/指数来源：{snap.source}",
        f"数据时间：{snap.data_timestamp.isoformat(sep=' ', timespec='minutes')}",
        f"数据状态：{fresh.status.value}",
    ]
    if bundle.fixture_label:
        provenance.insert(0, bundle.fixture_label)

    trade_today = "谨慎（仅研究/模拟）" if regime.max_primary_candidates > 0 else "否（NO TRADE）"
    if not fresh.live_decision_ok:
        if fresh.status == DataStatus.PREVIOUS_CLOSE:
            trade_today = "谨慎（盘前：基于上一交易日收盘数据，非盘中实时）"
        else:
            trade_today = "否（数据不够新，不适合盘中实盘决策）"

    direction = (
        "偏强" if (snap.sh_index_change_pct or 0) > 0.5
        else "偏弱" if (snap.sh_index_change_pct or 0) < -0.5
        else "震荡"
    )
    position = "0%" if regime.max_primary_candidates == 0 else "10%-20% 单票上限（模拟）"

    ranked_sectors = rank_sectors(bundle.sectors)
    sector_section = ranked_sectors
    strong_names = {s.name for s in ranked_sectors[:3]}

    primary: list[CandidatePlan] = []
    watchlist: list[CandidatePlan] = []
    avoid: list[str] = ["ST板块（默认回避）", "流动性极低个股", "涨停封板难以买入的标的"]

    can_select = regime.max_primary_candidates > 0 and (
        fresh.live_decision_ok or fresh.status == DataStatus.PREVIOUS_CLOSE
    )

    if can_select:
        screened = filter_universe(bundle.stocks, strong_names)
        scored: list[tuple[float, CandidatePlan, str]] = []
        for sr in screened:
            if not sr.passed:
                if sr.exclude_reason:
                    avoid.append(f"{sr.stock.name}({sr.stock.code})：{sr.exclude_reason}")
                continue
            st = sr.stock
            cat = assess_catalyst(
                st.official_catalyst or "none",
                social_media_only=st.rumor_only_catalyst,
                has_official_url=bool(st.official_catalyst),
            )
            sb = score_candidate(
                regime_fit=12 if regime.max_primary_candidates >= 2 else 8,
                sector_strength=12,
                trend_momentum=min(20, st.trend_score),
                volume_liquidity=8 if st.avg_daily_value_m >= 80 else 5,
                fundamental_quality=min(15, st.fundamental_score),
                valuation_context=min(10, st.valuation_score),
                confirmed_catalysts=8 if cat.usable_as_catalyst else 0,
                risk_control=4,
                overheated=st.change_pct > 8,
                weak_liquidity=st.avg_daily_value_m < 50,
                unverified_rumor=st.rumor_only_catalyst,
            )
            levels = compute_trade_levels(st)
            if not levels.acceptable:
                avoid.append(f"{st.name}：{levels.reject_reason}")
                continue
            plan = _stock_to_plan(st, sb.total, levels, regime)
            tier = sb.tier()
            if tier == "primary":
                scored.append((sb.total, plan, "primary"))
            elif tier == "watchlist":
                watchlist.append(plan)

        scored.sort(key=lambda x: x[0], reverse=True)
        primary = [p for _, p, _ in scored[: regime.max_primary_candidates]]

    report = DailyReport(
        conclusion_direction=direction,
        market_regime_zh=regime.regime.value,
        position_guidance=position,
        trade_today=trade_today,
        data_cutoff=snap.data_timestamp.isoformat(sep=" ", timespec="minutes"),
        data_status=fresh.status.value,
        one_liner=regime.guidance_zh,
        regime=regime,
        freshness=fresh,
        primary=primary,
        watchlist=watchlist[:5],
        avoid=avoid,
        sectors=sector_section,
        data_provenance=provenance,
        assumptions=bundle.assumptions or [
            "本报告使用确定性样本/fixture数据时，不代表实时行情",
            "评分为模型概率辅助，非收益保证",
        ],
    )
    return PipelineResult(report=report, data_provenance=provenance, assumptions=report.assumptions)


def load_bundle(fixture_name: str, fixtures_dir: Path) -> MarketBundle:
    return bundle_from_fixture(load_fixture(fixture_name, fixtures_dir))
