"""Full-universe intelligence pipeline v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from tools.china_quant.data import load_fixture
from tools.china_quant.freshness import DataStatus, assess_freshness
from tools.china_quant.institutional_flow import parse_institutional_payload, signals_for_code
from tools.china_quant.models import MarketBundle, StockRecord, bundle_from_fixture
from tools.china_quant.policy_monitor import parse_policy_payload, summarize_policy
from tools.china_quant.regime import classify_regime
from tools.china_quant.report import CandidatePlan, DailyReport
from tools.china_quant.risk import compute_trade_levels
from tools.china_quant.scoring_v2 import score_stock_v2
from tools.china_quant.sector_rotation import rank_sectors_v2
from tools.china_quant.dossier import render_dossier
from tools.china_quant.universe import build_universe


@dataclass
class IntelligenceResult:
    report: DailyReport
    dossiers: dict[str, str] = field(default_factory=dict)
    universe_stats: dict = field(default_factory=dict)
    policy_summary: str = ""
    institutional_count: int = 0
    mode: str = "FIXTURE"


def _inst_score(signals) -> float:
    if not signals:
        return 0.0
    confirmed = sum(1 for s in signals if s.disclosure_level == "confirmed")
    return min(5.0, confirmed * 2.5)


def _to_plan(stock: StockRecord, score, levels) -> CandidatePlan:
    return CandidatePlan(
        name=stock.name, code=stock.code, exchange=stock.exchange, sector=stock.sector,
        price=stock.price, data_time="fixture",
        recommendation="可轻仓试探" if score.total >= 78 else "观察",
        confidence="MEDIUM" if score.total >= 78 else "LOW", score=score.total,
        reasons=[f"综合评分{score.total:.0f}", f"板块{stock.sector}"],
        entry_range=f"{levels.entry_low:.2f}-{levels.entry_high:.2f}",
        entry_confirm=levels.entry_confirm, cancel_condition=levels.cancel_condition,
        stop=f"{levels.stop_price:.2f} (-{levels.stop_pct:.0f}%)",
        target1=f"{levels.target1:.2f}", target2=f"{levels.target2:.2f}",
        hold_period=levels.hold_period, position_pct=levels.position_pct,
        reward_risk=levels.reward_risk,
        catalyst=stock.official_catalyst or "无确认催化",
        risks=["板块轮动", "大盘风险"], invalidation=f"跌破{levels.stop_price:.2f}",
    )


def run_intelligence(
    bundle: MarketBundle,
    *,
    fixtures_dir: Path,
    policy_data: dict | None = None,
    inst_data: dict | None = None,
    now: Optional[datetime] = None,
) -> IntelligenceResult:
    snap = bundle.snapshot
    fresh = assess_freshness(snap.data_timestamp, now=now)
    regime = classify_regime(snap.sh_index_change_pct, snap.advance_count, snap.decline_count)

    policy_items = parse_policy_payload(policy_data or {"items": []})
    policy_summary = summarize_policy(policy_items)
    inst_signals = parse_institutional_payload(inst_data or {"signals": []})

    rot = rank_sectors_v2(bundle.sectors)
    uni = build_universe({"stocks": [_stock_dict(s) for s in bundle.stocks]}, strong_sectors=rot.top_names)

    stale = not fresh.live_decision_ok and fresh.status != DataStatus.PREVIOUS_CLOSE
    can_select = regime.max_primary_candidates > 0 and not stale

    primary: list[CandidatePlan] = []
    watchlist: list[CandidatePlan] = []
    avoid = ["ST默认排除", "停牌", "涨停", "低流动性", "传闻催化"]
    dossiers: dict[str, str] = {}

    for st, reason in uni.excluded:
        avoid.append(f"{st.name}({st.code})：{reason}")

    if can_select:
        ranked: list[tuple[float, StockRecord, object]] = []
        for st in uni.tradable:
            sigs = signals_for_code(inst_signals, st.code)
            fs = score_stock_v2(
                st, regime_name=regime.regime.value, sector_strength=12.0,
                has_confirmed_catalyst=bool(st.official_catalyst),
                institutional_score=_inst_score(sigs), stale=stale,
            )
            levels = compute_trade_levels(st)
            if not levels.acceptable:
                avoid.append(f"{st.name}：{levels.reject_reason}")
                continue
            tier = fs.tier(regime.regime.value)
            if tier == "primary":
                ranked.append((fs.total, st, fs))
            elif tier == "watchlist":
                watchlist.append(_to_plan(st, fs, levels))
        ranked.sort(key=lambda x: x[0], reverse=True)
        for i, (_, st, fs) in enumerate(ranked[: regime.max_primary_candidates], 1):
            levels = compute_trade_levels(st)
            primary.append(_to_plan(st, fs, levels))
            inst_sum = "; ".join(f"{s.signal_type}:{s.value}" for s in signals_for_code(inst_signals, st.code)) or "无公开披露"
            dossiers[st.code] = render_dossier(
                st, fs, levels, rank=i, regime=regime.regime.value,
                sector_stage=next((s.phase for s in rot.ranked if s.name == st.sector), "mature"),
                policy_summary=policy_summary, institutional_summary=inst_sum,
                data_freshness=fresh.status.value,
            )

    trade_today = "否（NO TRADE）" if regime.max_primary_candidates == 0 else "谨慎（纸面交易/模拟）"
    if stale:
        trade_today = "否（数据不够新，不适合盘中实盘决策）"
    elif fresh.status == DataStatus.PREVIOUS_CLOSE:
        trade_today = "谨慎（盘前：上一交易日收盘数据）"

    report = DailyReport(
        conclusion_direction="偏强" if (snap.sh_index_change_pct or 0) > 0.5 else "震荡",
        market_regime_zh=regime.regime.value,
        position_guidance="0%" if not primary else "10%-15%单票上限",
        trade_today=trade_today,
        data_cutoff=snap.data_timestamp.isoformat(sep=" ", timespec="minutes"),
        data_status=fresh.status.value,
        one_liner=regime.guidance_zh,
        regime=regime, freshness=fresh,
        primary=primary, watchlist=watchlist[:5], avoid=avoid,
        sectors=rot.ranked,
        data_provenance=[bundle.fixture_label or "fixture", f"universe={uni.stats.total}", f"tradable={len(uni.tradable)}"],
        assumptions=bundle.assumptions or ["样本/fixture模式"],
        policy_summary=policy_summary,
        institutional_summary=f"{len(inst_signals)}条公开信号（样本）",
    )
    return IntelligenceResult(
        report=report, dossiers=dossiers,
        universe_stats={"total": uni.stats.total, "tradable": len(uni.tradable), "excluded": len(uni.excluded)},
        policy_summary=policy_summary, institutional_count=len(inst_signals), mode="FIXTURE",
    )


def _stock_dict(st: StockRecord) -> dict:
    from dataclasses import asdict
    return asdict(st)


def load_full_bundle(fixtures_dir: Path, name: str = "universe_full") -> MarketBundle:
    return bundle_from_fixture(load_fixture(name, fixtures_dir))
