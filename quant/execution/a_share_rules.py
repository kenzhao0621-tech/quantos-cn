"""ExecutionOS — A-share trading rules (delegates to tradability mask + paper engine)."""

from __future__ import annotations

from typing import Any

LOT_SIZE = 100


def validate_order(
    *,
    symbol: str,
    side: str,
    qty: int,
    price: float,
    last_pct: float,
    avg_amount: float,
    cash: float,
    is_st: bool = False,
    is_suspended: bool = False,
) -> dict[str, Any]:
    from quant.tradability.mask import evaluate_tradability

    reasons: list[str] = []
    if qty <= 0 or qty % LOT_SIZE != 0:
        reasons.append("invalid_lot_size")
    if is_st:
        reasons.append("st_forbidden")
    if is_suspended:
        reasons.append("suspended")
    mask = evaluate_tradability(
        symbol=symbol,
        last_close=price,
        last_pct=last_pct,
        avg_amount=avg_amount,
        capital_cny=cash,
    )
    if side.upper() == "BUY" and not mask.valid_for_purchase:
        reasons.extend(list(mask.blockers) or ["not_buyable"])
    if side.upper() == "SELL" and last_pct <= -9.8:
        reasons.append("limit_down_unsellable")
    cost = qty * price
    if side.upper() == "BUY" and cost > cash:
        reasons.append("insufficient_cash")
    return {
        "valid": not reasons,
        "reasons": reasons,
        "lot_size": LOT_SIZE,
        "t_plus_1": True,
        "commission_bps": 3,
        "stamp_tax_bps_sell": 5,
        "transfer_fee_bps": 0.2,
    }


def a_share_rules_summary() -> dict[str, Any]:
    return {
        "t_plus_1": True,
        "lot_size": LOT_SIZE,
        "limit_up_pct": 9.8,
        "limit_down_pct": -9.8,
        "st_limit_pct": 4.9,
        "commission_bps": 3,
        "stamp_tax_bps_sell": 5,
        "slippage_bps_default": 12,
    }
