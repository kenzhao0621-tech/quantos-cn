"""Integer-constrained allocation for small capital (e.g. RMB 5,000)."""

from __future__ import annotations

from typing import Any


def affordable_lots(price: float, capital_cny: float, profile: str = "paper") -> tuple[int, float]:
    """Return (max whole lots, max position cny) affordable after fees."""
    from quant.portfolio.cost_model import estimate_round_trip_cost_cny

    if price <= 0 or capital_cny <= 0:
        return 0, 0.0
    lots = 0
    while True:
        next_lots = lots + 1
        cost = price * 100 * next_lots + estimate_round_trip_cost_cny(price, next_lots, profile) * 0.5
        if cost > capital_cny:
            break
        lots = next_lots
        if lots >= 50:
            break
    return lots, round(price * 100 * lots, 2) if lots else 0.0


def allocate_top_k(
    candidates: list[dict[str, Any]],
    *,
    capital_cny: float = 5000.0,
    max_holdings: int = 2,
    max_per_position_pct: float = 0.6,
) -> list[dict[str, Any]]:
    """Greedy integer allocation by final_score."""
    remaining = capital_cny
    out: list[dict[str, Any]] = []
    sorted_c = sorted(candidates, key=lambda x: x.get("final_score", x.get("score", 0)), reverse=True)
    for c in sorted_c:
        if len(out) >= max_holdings or remaining <= 0:
            break
        if not c.get("valid_for_purchase"):
            continue
        price = float(c.get("last_close") or c.get("live_price") or 0)
        cap_for_pos = min(remaining, capital_cny * max_per_position_pct)
        lots, pos_cny = affordable_lots(price, cap_for_pos)
        if lots < 1:
            continue
        out.append({
            "symbol": c["symbol"],
            "lots": lots,
            "quantity": lots * 100,
            "position_cny": pos_cny,
            "allocation_pct": round(pos_cny / capital_cny * 100, 1),
        })
        remaining -= pos_cny
    return out
