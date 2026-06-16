"""A-share market rules — static reference + runtime checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Board(str, Enum):
    MAIN_SH = "主板-上交所"
    MAIN_SZ = "主板-深交所"
    STAR = "科创板"
    CHINEXT = "创业板"
    BSE = "北交所"


# Price limit pct by board (simplified; ST uses 5%)
LIMIT_PCT = {
    Board.MAIN_SH: 0.10,
    Board.MAIN_SZ: 0.10,
    Board.STAR: 0.20,
    Board.CHINEXT: 0.20,
    Board.BSE: 0.30,
}

ST_LIMIT_PCT = 0.05
LOT_SIZE = 100  # shares per lot (standard A-share)


@dataclass
class TradeabilityCheck:
    tradable: bool
    warnings: list[str]
    block_reason: Optional[str] = None


def check_entry_feasible(
    *,
    suspended: bool = False,
    is_st: bool = False,
    at_limit_up: bool = False,
    at_limit_down: bool = False,
    newly_listed_days: int = 999,
    min_history_days: int = 60,
) -> TradeabilityCheck:
    warnings: list[str] = []
    if suspended:
        return TradeabilityCheck(False, warnings, "股票停牌，无法交易")
    if at_limit_up:
        return TradeabilityCheck(False, warnings, "涨停封板， realistically 难以买入")
    if at_limit_down:
        warnings.append("接近或处于跌停，退出风险高")
    if newly_listed_days < min_history_days:
        warnings.append(f"上市不足{min_history_days}日，历史数据不足")
    if is_st:
        warnings.append("ST股票，波动与退市风险更高（默认不推荐除非用户明确要求）")
    if warnings and not any("无法" in w for w in warnings):
        return TradeabilityCheck(True, warnings)
    if warnings:
        return TradeabilityCheck(len(warnings) == 0 or "退出" in warnings[0], warnings)
    return TradeabilityCheck(True, warnings)


def limit_pct(board: Board, is_st: bool) -> float:
    if is_st:
        return ST_LIMIT_PCT
    return LIMIT_PCT.get(board, 0.10)


def t_plus_one_note() -> str:
    return "A股股票实行T+1：当日买入的股票，下一个交易日才能卖出。"
