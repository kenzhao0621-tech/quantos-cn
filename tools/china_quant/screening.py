"""Stock universe filtering."""

from __future__ import annotations

from dataclasses import dataclass

from tools.china_quant.models import StockRecord
from tools.china_quant.rules import Board, check_entry_feasible


MIN_DAILY_VALUE_M = 30.0


@dataclass
class ScreenResult:
    stock: StockRecord
    passed: bool
    exclude_reason: str = ""
    warnings: list[str] | None = None


def screen_stock(stock: StockRecord, strong_sectors: set[str]) -> ScreenResult:
    warnings: list[str] = []
    chk = check_entry_feasible(
        suspended=stock.suspended,
        is_st=stock.is_st,
        at_limit_up=stock.at_limit_up,
        at_limit_down=stock.at_limit_down,
        newly_listed_days=stock.newly_listed_days,
    )
    if not chk.tradable:
        return ScreenResult(stock, False, chk.block_reason or "不可交易")
    if stock.avg_daily_value_m < MIN_DAILY_VALUE_M:
        return ScreenResult(stock, False, "流动性不足")
    if stock.sector not in strong_sectors:
        return ScreenResult(stock, False, "板块不在强势名单")
    if stock.rumor_only_catalyst and not stock.official_catalyst:
        return ScreenResult(stock, False, "仅传闻催化，不可用")
    if stock.is_st:
        return ScreenResult(stock, False, "ST默认回避")
    warnings.extend(chk.warnings)
    return ScreenResult(stock, True, warnings=warnings)


def filter_universe(stocks: list[StockRecord], strong_sectors: set[str]) -> list[ScreenResult]:
    return [screen_stock(s, strong_sectors) for s in stocks]
