"""Buy/sell zone estimates from price, trend (vs MA20), and volatility — not price targets."""

from __future__ import annotations

from typing import Any


def _limit_pct(symbol: str) -> float:
    code = symbol.split(".")[0]
    if code.startswith(("30", "688")):
        return 0.20
    return 0.10


def compute_trade_zones(
    *,
    symbol: str,
    price: float,
    trend_pct: float,
    vol_20: float,
    last_pct: float = 0.0,
) -> dict[str, Any]:
    """Return conservative buy/sell bands for beginners (research only)."""
    if price <= 0:
        return {}
    trend_ratio = float(trend_pct) / 100.0
    ma20 = price / (1.0 + trend_ratio) if abs(1.0 + trend_ratio) > 1e-6 else price
    vol = max(0.5, float(vol_20 or 2.0))
    limit = _limit_pct(symbol)
    limit_up = round(price * (1.0 + limit * 0.995), 2)
    limit_down = round(price * (1.0 - limit * 0.995), 2)

    # Buy: prefer pullback toward MA20, never chase limit-up
    ideal_buy = min(price, ma20 * 1.02)
    buy_low = round(max(limit_down, ideal_buy * (1.0 - vol * 0.008), price * 0.96), 2)
    buy_high = round(min(price * 1.005, ma20 * 1.04, limit_up * 0.92), 2)
    if buy_low > buy_high:
        buy_low, buy_high = round(price * 0.98, 2), round(price * 1.01, 2)

    # Sell / take-profit zone
    sell_low = round(price * (1.0 + max(0.02, vol * 0.006)), 2)
    sell_high = round(min(price * (1.0 + max(0.05, vol * 0.012)), limit_up * 0.98), 2)

    stop_loss = round(max(limit_down, price * (1.0 - max(0.05, vol * 0.015))), 2)
    take_profit = sell_high

    chase_warning = float(last_pct) >= 9.0 or buy_high >= limit_up * 0.95

    return {
        "reference_price": round(price, 2),
        "ma20_estimate": round(ma20, 2),
        "buy_zone_low": buy_low,
        "buy_zone_high": buy_high,
        "sell_zone_low": sell_low,
        "sell_zone_high": sell_high,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "limit_up_approx": limit_up,
        "limit_down_approx": limit_down,
        "chase_warning": chase_warning,
        "disclaimer": "区间为系统根据历史波动估算，非盈利承诺；涨停附近不建议买入。",
    }
