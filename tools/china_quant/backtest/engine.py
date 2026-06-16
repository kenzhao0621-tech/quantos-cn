"""Backtest engine — long-only with T+1, limits, costs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.china_quant.config import DEFAULT_RISK, RiskConfig


@dataclass
class BacktestTrade:
    date: str
    code: str
    action: str
    price: float
    shares: int
    cost: float
    reason: str = ""


@dataclass
class BacktestResult:
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[tuple[str, float]] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    validation_label: str = "PRELIMINARY"
    bias_warnings: list[str] = field(default_factory=list)


def run_backtest(
    bars: list[dict[str, Any]],
    *,
    initial_cash: float = 1_000_000,
    cfg: RiskConfig = DEFAULT_RISK,
) -> BacktestResult:
    """Simple momentum long-only backtest on daily bars."""
    result = BacktestResult()
    cash = initial_cash
    position = 0
    entry_price = 0.0
    pending_sell = False

    for i, bar in enumerate(bars):
        date = str(bar.get("date", bar.get("日期", "")))
        close = float(bar.get("close", bar.get("收盘", 0)))
        pct = float(bar.get("pct_chg", bar.get("涨跌幅", 0)))
        suspended = bar.get("suspended", False)
        at_limit_up = pct >= 9.9
        at_limit_down = pct <= -9.9

        if pending_sell and position > 0 and not suspended and not at_limit_down:
            slip = close * (1 - cfg.slippage_bps / 10000)
            proceeds = position * slip * (1 - cfg.commission - cfg.stamp_duty_sell)
            cash += proceeds
            result.trades.append(BacktestTrade(date, bars[0].get("code", ""), "SELL", slip, position, proceeds))
            position = 0
            pending_sell = False

        if position == 0 and i >= 20 and not suspended and not at_limit_up:
            ma20 = sum(float(bars[j].get("close", b.get("收盘", 0))) for j, b in enumerate(bars[i - 20 : i])) / 20
            if close > ma20 and pct > 0:
                slip = close * (1 + cfg.slippage_bps / 10000)
                shares = int(cash * 0.1 / slip / 100) * 100
                if shares >= 100:
                    cost = shares * slip * (1 + cfg.commission)
                    if cost <= cash:
                        cash -= cost
                        position = shares
                        entry_price = slip
                        result.trades.append(BacktestTrade(date, bars[0].get("code", ""), "BUY", slip, shares, cost))
                        pending_sell = True  # T+1: sell next valid day

        eq = cash + position * close
        result.equity_curve.append((date, eq))

    if result.equity_curve:
        start = result.equity_curve[0][1]
        end = result.equity_curve[-1][1]
        ret = (end - start) / start if start else 0
        peak = start
        max_dd = 0.0
        for _, v in result.equity_curve:
            peak = max(peak, v)
            max_dd = max(max_dd, (peak - v) / peak if peak else 0)
        wins = sum(1 for t in result.trades if t.action == "SELL" and t.price > entry_price)
        sells = sum(1 for t in result.trades if t.action == "SELL")
        result.metrics = {
            "total_return": ret,
            "max_drawdown": max_dd,
            "trade_count": len(result.trades),
            "win_rate": wins / sells if sells else 0,
        }
    result.bias_warnings = ["Fixture/historical only; walk-forward required for VALIDATED"]
    return result


def walk_forward_split(bars: list[dict], train_ratio: float = 0.7) -> tuple[list, list]:
    cut = int(len(bars) * train_ratio)
    return bars[:cut], bars[cut:]
