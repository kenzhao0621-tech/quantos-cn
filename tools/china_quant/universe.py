"""Full A-share universe construction and filtering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.china_quant.models import StockRecord


MIN_DAILY_VALUE_M = 30.0
MIN_LISTING_DAYS = 60


@dataclass
class UniverseStats:
    total: int = 0
    after_hard_exclusion: int = 0
    after_liquidity: int = 0
    after_sector: int = 0
    exclusion_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class UniverseResult:
    all_stocks: list[StockRecord]
    tradable: list[StockRecord]
    excluded: list[tuple[StockRecord, str]]
    stats: UniverseStats


def _from_dict(d: dict[str, Any]) -> StockRecord:
    return StockRecord(
        code=d["code"],
        name=d["name"],
        exchange=d.get("exchange", "SH"),
        board=d.get("board", "MAIN_SH"),
        sector=d.get("sector", "未知"),
        price=float(d.get("price", 0)),
        change_pct=float(d.get("change_pct", 0)),
        avg_daily_value_m=float(d.get("avg_daily_value_m", 0)),
        is_st=d.get("is_st", False),
        suspended=d.get("suspended", False),
        at_limit_up=d.get("at_limit_up", False),
        at_limit_down=d.get("at_limit_down", False),
        newly_listed_days=int(d.get("newly_listed_days", 999)),
        rumor_only_catalyst=d.get("rumor_only_catalyst", False),
        official_catalyst=d.get("official_catalyst", ""),
        trend_score=float(d.get("trend_score", 0)),
        fundamental_score=float(d.get("fundamental_score", 0)),
        valuation_score=float(d.get("valuation_score", 0)),
    )


def build_universe(payload: dict[str, Any], *, strong_sectors: set[str] | None = None) -> UniverseResult:
    stocks = [_from_dict(s) for s in payload.get("stocks", [])]
    stats = UniverseStats(total=len(stocks))
    excluded: list[tuple[StockRecord, str]] = []
    tradable: list[StockRecord] = []

    for st in stocks:
        reason = _hard_exclude(st)
        if reason:
            excluded.append((st, reason))
            stats.exclusion_counts[reason] = stats.exclusion_counts.get(reason, 0) + 1
            continue
        if st.avg_daily_value_m < MIN_DAILY_VALUE_M:
            excluded.append((st, "流动性不足"))
            stats.exclusion_counts["流动性不足"] = stats.exclusion_counts.get("liquidity", 0) + 1
            continue
        stats.after_liquidity += 1
        if strong_sectors and st.sector not in strong_sectors:
            excluded.append((st, "板块不在强势名单"))
            continue
        tradable.append(st)

    stats.after_hard_exclusion = stats.total - sum(
        1 for _, r in excluded if r not in ("流动性不足", "板块不在强势名单")
    )
    stats.after_sector = len(tradable)
    return UniverseResult(stocks, tradable, excluded, stats)


def _hard_exclude(st: StockRecord) -> str | None:
    if st.suspended:
        return "停牌"
    if st.is_st:
        return "ST默认排除"
    if st.at_limit_up:
        return "涨停无法买入"
    if st.newly_listed_days < MIN_LISTING_DAYS:
        return "上市历史不足"
    if st.rumor_only_catalyst and not st.official_catalyst:
        return "仅传闻催化"
    if st.price <= 0:
        return "无效价格"
    return None
