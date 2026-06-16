"""Entry, stop, target, and position sizing."""

from __future__ import annotations

from dataclasses import dataclass

from tools.china_quant.models import StockRecord
from tools.china_quant.rules import LOT_SIZE, Board, limit_pct


@dataclass
class TradeLevels:
    entry_low: float
    entry_high: float
    entry_confirm: str
    cancel_condition: str
    stop_price: float
    stop_pct: float
    target1: float
    target2: float
    hold_period: str
    position_pct: str
    reward_risk: str
    acceptable: bool
    reject_reason: str = ""


def _board_enum(board: str) -> Board:
    mapping = {
        "MAIN_SH": Board.MAIN_SH,
        "MAIN_SZ": Board.MAIN_SZ,
        "STAR": Board.STAR,
        "CHINEXT": Board.CHINEXT,
        "BSE": Board.BSE,
    }
    return mapping.get(board, Board.MAIN_SH)


def compute_trade_levels(stock: StockRecord, *, max_position_pct: float = 15.0) -> TradeLevels:
    p = stock.price
    lp = limit_pct(_board_enum(stock.board), stock.is_st)
    entry_low = round(p * 0.985, 2)
    entry_high = round(p * 1.01, 2)
    stop_pct = 0.06 if not stock.is_st else 0.08
    stop_price = round(p * (1 - stop_pct), 2)
    target1 = round(p * (1 + stop_pct * 1.6), 2)  # min ~1.6:1 vs stop
    target2 = round(p * (1 + stop_pct * 2.8), 2)
    risk = p - stop_price
    reward = target1 - p
    rr = reward / risk if risk > 0 else 0
    acceptable = rr >= 1.5 and risk > 0
    reject = ""
    if rr < 1.5:
        reject = "盈亏比低于1.5:1，不符合风控"
        acceptable = False
    if stock.at_limit_up:
        acceptable = False
        reject = "涨停无法买入"
    return TradeLevels(
        entry_low=entry_low,
        entry_high=entry_high,
        entry_confirm=f"放量站稳 {entry_high:.2f} 且板块维持强势",
        cancel_condition=f"跌破 {round(p * 0.97, 2)} 或板块转弱",
        stop_price=stop_price,
        stop_pct=stop_pct * 100,
        target1=target1,
        target2=target2,
        hold_period="3-7个交易日（模拟）",
        position_pct=f"{max_position_pct:.0f}%",
        reward_risk=f"1:{rr:.1f}" if rr else "N/A",
        acceptable=acceptable,
        reject_reason=reject,
    )
