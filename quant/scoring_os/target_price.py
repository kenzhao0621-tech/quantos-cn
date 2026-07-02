"""Buy zone / stop loss / target price from price structure — never LLM-written (v2.2 §7).

    BuyZoneLow  = max(key support, MA20-area support, risk-derived stop reverse)
    BuyZoneHigh = min(reasonable pullback vs price, breakout confirm, R:R-allowed price)
    StopLoss    = max(structural stop, ATR stop, account max-loss reverse stop)
    Target1     = min(recent high resistance, box top, Entry + 1.5R)
    Target2     = min(higher-timeframe resistance, Entry + 2.5R [, model upper bound])
    R           = Entry − StopLoss

All bands derive from real OHLCV history passed in by the caller. If structure
is insufficient (too little history, no upside room, price too far from a sane
entry) the plan honestly says wait / do-not-buy instead of inventing numbers.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional

ATR_PERIOD = 14
ATR_MULTIPLIER_CONSERVATIVE = 1.5
ATR_MULTIPLIER_NORMAL = 2.0
MAX_LOSS_PER_TRADE_DEFAULT = 0.02  # of account, within the 0.01-0.03 spec band
MIN_RISK_REWARD = 1.5
LOT_SIZE = 100


def _limit_pct(symbol: str) -> float:
    code = symbol.split(".")[0]
    if code.startswith(("30", "688")):
        return 0.20
    if code.startswith(("8", "4")):
        return 0.30
    return 0.10


def compute_atr(history: List[Dict[str, Any]], period: int = ATR_PERIOD) -> Optional[float]:
    """ATR over daily bars (chronological order). None when history is short."""
    bars = [b for b in history if b.get("high") and b.get("low") and b.get("close")]
    if len(bars) < period + 1:
        return None
    trs = []
    for prev, cur in zip(bars[:-1], bars[1:]):
        h, l, pc = float(cur["high"]), float(cur["low"]), float(prev["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    recent = trs[-period:]
    return statistics.fmean(recent) if recent else None


def _support_resistance(history: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    closes = [float(b["close"]) for b in history if b.get("close")]
    lows = [float(b["low"]) for b in history if b.get("low")]
    highs = [float(b["high"]) for b in history if b.get("high")]
    if len(closes) < 20:
        return {"support_20": None, "support_60": None, "resistance_20": None,
                "resistance_60": None, "ma20": None}
    return {
        "support_20": min(lows[-20:]) if len(lows) >= 20 else None,
        "support_60": min(lows[-60:]) if len(lows) >= 60 else None,
        "resistance_20": max(highs[-20:]) if len(highs) >= 20 else None,
        "resistance_60": max(highs[-60:]) if len(highs) >= 60 else None,
        "ma20": statistics.fmean(closes[-20:]),
    }


def build_trade_plan(
    *,
    symbol: str,
    current_price: float,
    history: List[Dict[str, Any]],
    capital_cny: float = 10000.0,
    position_weight: float = 0.30,
    max_loss_per_trade: float = MAX_LOSS_PER_TRADE_DEFAULT,
    conservative: bool = True,
    model_upper_bound: Optional[float] = None,
    last_pct: float = 0.0,
    open_gap_pct: float = 0.0,
) -> Dict[str, Any]:
    """Return the v2.2 §7.4 executable-plan block (prices only; no advice text).

    ``history`` must be chronological daily bars with open/high/low/close.
    Returns action="insufficient_structure" when price structure cannot support
    an honest plan.
    """
    if current_price <= 0 or len(history) < 21:
        return _no_plan(symbol, current_price, "历史K线不足（<21根），无法计算价格结构")

    atr = compute_atr(history)
    levels = _support_resistance(history)
    ma20 = levels["ma20"]
    if atr is None or ma20 is None:
        return _no_plan(symbol, current_price, "ATR/均线结构数据不足")

    limit = _limit_pct(symbol)
    k = ATR_MULTIPLIER_CONSERVATIVE if conservative else ATR_MULTIPLIER_NORMAL

    # ---- Stop loss: max of structural / ATR / account-risk stops (§7.2) ----
    structural_stop = levels["support_20"]
    entry_ref = min(current_price, ma20 * 1.02)
    atr_stop = entry_ref - k * atr
    pw = max(0.05, min(1.0, position_weight))
    account_risk_stop = entry_ref * (1.0 - max_loss_per_trade / pw)
    stop_candidates = [s for s in (structural_stop, atr_stop, account_risk_stop) if s and s > 0]
    stop_loss = max(stop_candidates)
    if stop_loss >= entry_ref:
        return _no_plan(symbol, current_price, "止损位高于合理入场价，结构不成立")

    # ---- Buy zone (§7.1) ----
    support = max(x for x in (levels["support_20"], ma20 * 0.97) if x)
    buy_low = max(support, stop_loss * 1.01)
    r_unit_at_high = None
    resistance = levels["resistance_20"] or current_price
    buy_high_candidates = [current_price * 1.01, ma20 * 1.05]
    # R:R-allowed price: entry such that (Target1 − entry) / (entry − stop) >= MIN_RISK_REWARD
    t1_cap = resistance
    rr_allowed_entry = (t1_cap + MIN_RISK_REWARD * stop_loss) / (1.0 + MIN_RISK_REWARD)
    if rr_allowed_entry > stop_loss:
        buy_high_candidates.append(rr_allowed_entry)
    buy_high = min(buy_high_candidates)
    if buy_high <= buy_low:
        return _wait_plan(symbol, current_price, stop_loss, levels,
                          "现价距离合理买点过远或收益风险比不足 — 等待回调")

    entry = min(current_price, (buy_low + buy_high) / 2.0)
    if entry <= stop_loss:
        return _no_plan(symbol, current_price, "入场价低于止损价，结构不成立")
    r_unit = entry - stop_loss

    # ---- Targets (§7.3) ----
    target_1 = min(x for x in (resistance, entry + 1.5 * r_unit) if x)
    t2_candidates = [entry + 2.5 * r_unit]
    if levels["resistance_60"]:
        t2_candidates.append(levels["resistance_60"])
    if model_upper_bound and model_upper_bound > entry:
        t2_candidates.append(model_upper_bound)
    target_2 = min(t2_candidates)
    if target_2 < target_1:
        target_1, target_2 = target_2, target_1

    risk_reward = (target_1 - entry) / r_unit if r_unit > 0 else 0.0
    if target_1 <= entry or risk_reward < 1.0:
        return _wait_plan(symbol, current_price, stop_loss, levels,
                          "上方空间不足（目标价距离入场价过近），今日不推荐买入")

    # ---- Position sizing under A-share lot rules ----
    budget = capital_cny * pw
    shares = int(budget / (entry * LOT_SIZE)) * LOT_SIZE
    lot_warning = ""
    if shares < LOT_SIZE:
        lot_warning = f"资金不足一手：{symbol} 一手（100股）约需 {entry * LOT_SIZE:.0f} 元"
        shares = 0
    position_size_rmb = round(shares * entry, 2)

    do_not_buy = _do_not_buy_conditions(symbol, current_price, limit,
                                        last_pct=last_pct, open_gap_pct=open_gap_pct)
    recommendation = "buy_zone" if shares > 0 and not do_not_buy else "watch"

    return {
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "recommendation": recommendation,
        "buy_zone": [round(buy_low, 2), round(buy_high, 2)],
        "aggressive_entry": round(min(buy_high, current_price), 2),
        "conservative_entry": round(buy_low, 2),
        "stop_loss": round(stop_loss, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "risk_reward_ratio": round(risk_reward, 2),
        "expected_upside_range": f"{(target_1 / entry - 1) * 100:.1f}% ~ {(target_2 / entry - 1) * 100:.1f}%",
        "downside_risk_range": f"-{(1 - stop_loss / entry) * 100:.1f}%",
        "position_size_rmb": position_size_rmb,
        "position_weight": pw,
        "shares": shares,
        "minimum_lot_warning": lot_warning,
        "do_not_buy_conditions": do_not_buy or _standing_do_not_buy(limit),
        "basis": {
            "atr_14": round(atr, 3),
            "atr_multiplier": k,
            "ma20": round(ma20, 2),
            "support_20d": round(levels["support_20"], 2) if levels["support_20"] else None,
            "support_60d": round(levels["support_60"], 2) if levels["support_60"] else None,
            "resistance_20d": round(levels["resistance_20"], 2) if levels["resistance_20"] else None,
            "resistance_60d": round(levels["resistance_60"], 2) if levels["resistance_60"] else None,
            "stop_components": {
                "structural_stop": round(structural_stop, 2) if structural_stop else None,
                "atr_stop": round(atr_stop, 2),
                "account_risk_stop": round(account_risk_stop, 2),
            },
            "max_loss_per_trade": max_loss_per_trade,
            "r_unit": round(r_unit, 3),
            "model_upper_bound_used": bool(model_upper_bound and abs(target_2 - model_upper_bound) < 1e-9),
            "note": "目标价若来自模型预测上沿，属于不确定预测，不保证发生",
        },
        "method": "price_structure_v2.2 (support/resistance + ATR + account-risk reverse)",
    }


def _do_not_buy_conditions(symbol: str, price: float, limit: float, *,
                           last_pct: float, open_gap_pct: float) -> List[str]:
    conditions = []
    if last_pct >= limit * 100 * 0.95:
        conditions.append("接近或已涨停，无法以合理价格成交，禁止追入")
    if open_gap_pct > 5.0:
        conditions.append("高开超过 5%，不追高，等待回落确认")
    return conditions


def _standing_do_not_buy(limit: float) -> List[str]:
    return [
        f"若开盘高开超过 5% 或涨幅接近 {limit * 100:.0f}% 涨停价，不追入",
        "若跌破止损价，无条件退出计划，不补仓摊低",
        "若成交量异常放大且冲高回落（长上影），当日放弃买入",
    ]


def _wait_plan(symbol: str, price: float, stop_loss: float, levels: Dict[str, Any],
               reason: str) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "current_price": round(price, 2),
        "recommendation": "watch",
        "buy_zone": None,
        "stop_loss": round(stop_loss, 2) if stop_loss else None,
        "target_1": None,
        "target_2": None,
        "risk_reward_ratio": None,
        "shares": 0,
        "position_size_rmb": 0,
        "do_not_buy_conditions": [reason],
        "reason": reason,
        "basis": {"ma20": round(levels["ma20"], 2) if levels.get("ma20") else None},
        "method": "price_structure_v2.2",
    }


def _no_plan(symbol: str, price: float, reason: str) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "current_price": round(price, 2) if price else None,
        "recommendation": "insufficient_structure",
        "buy_zone": None,
        "stop_loss": None,
        "target_1": None,
        "target_2": None,
        "risk_reward_ratio": None,
        "shares": 0,
        "position_size_rmb": 0,
        "do_not_buy_conditions": [reason],
        "reason": reason,
        "method": "price_structure_v2.2",
    }
