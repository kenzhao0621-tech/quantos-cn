"""A-share transaction cost model — research / paper / live profiles."""

from __future__ import annotations

from typing import Any

PROFILES: dict[str, dict[str, float]] = {
    "research": {"commission_bps": 2.5, "min_commission": 5.0, "stamp_duty_bps": 5.0, "transfer_bps": 0.2, "slippage_bps": 8.0},
    "paper": {"commission_bps": 2.5, "min_commission": 5.0, "stamp_duty_bps": 5.0, "transfer_bps": 0.2, "slippage_bps": 12.0},
    "live": {"commission_bps": 2.5, "min_commission": 5.0, "stamp_duty_bps": 5.0, "transfer_bps": 0.2, "slippage_bps": 15.0},
}


def estimate_round_trip_cost_cny(price: float, lots: int = 1, profile: str = "paper") -> float:
    p = PROFILES.get(profile, PROFILES["paper"])
    notional = price * 100 * lots
    buy_comm = max(notional * p["commission_bps"] / 10000, p["min_commission"])
    sell_comm = max(notional * p["commission_bps"] / 10000, p["min_commission"])
    stamp = notional * p["stamp_duty_bps"] / 10000  # sell side
    transfer = notional * p["transfer_bps"] / 10000 * 2
    slip = notional * p["slippage_bps"] / 10000 * 2
    return round(buy_comm + sell_comm + stamp + transfer + slip, 2)


def cost_breakdown(price: float, lots: int = 1, profile: str = "paper") -> dict[str, Any]:
    p = PROFILES.get(profile, PROFILES["paper"])
    notional = price * 100 * lots
    return {
        "notional_cny": round(notional, 2),
        "commission_buy": round(max(notional * p["commission_bps"] / 10000, p["min_commission"]), 2),
        "commission_sell": round(max(notional * p["commission_bps"] / 10000, p["min_commission"]), 2),
        "stamp_duty_sell": round(notional * p["stamp_duty_bps"] / 10000, 2),
        "transfer_fee": round(notional * p["transfer_bps"] / 10000 * 2, 2),
        "slippage_round_trip": round(notional * p["slippage_bps"] / 10000 * 2, 2),
        "total_round_trip": estimate_round_trip_cost_cny(price, lots, profile),
        "profile": profile,
    }
