"""Unified portfolio: optimizer weights + integer lot allocation."""

from __future__ import annotations

from typing import Any

from quant.portfolio.allocator import affordable_lots
from quant.portfolio.constraints import DEFAULT_CONSTRAINTS
from quant.portfolio.optimizer import optimize_topk


def build_portfolio_allocation(
    candidates: list[dict[str, Any]],
    *,
    capital_cny: float,
    max_holdings: int | None = None,
    regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Single path for screener, paper, autopilot, and live execution."""
    cap = float(capital_cny or 5000.0)
    max_k = max(1, min(max_holdings or 5, 20))
    regime_scale = (0.5, 0.8)
    if regime:
        lo = float(regime.get("position_scale_min") or 0.5)
        hi = float(regime.get("position_scale_max") or 0.8)
        regime_scale = (lo, hi)

    purchasable = [c for c in candidates if c.get("valid_for_purchase", True)]
    if not purchasable:
        purchasable = list(candidates)

    opt = optimize_topk(
        purchasable,
        top_k=max_k,
        max_single_weight=DEFAULT_CONSTRAINTS.max_single_weight,
        max_industry_weight=DEFAULT_CONSTRAINTS.max_industry_weight,
        regime_position_scale=regime_scale,
    )

    positions: list[dict[str, Any]] = []
    blockers: list[str] = []
    sym_map = {c["symbol"]: c for c in purchasable}

    for p in opt.get("positions") or []:
        sym = p["symbol"]
        c = sym_map.get(sym)
        if not c:
            continue
        price = float(c.get("live_price") or c.get("last_close") or 0)
        if price <= 0:
            blockers.append(f"{sym}: no price")
            continue
        if c.get("live_pct") is not None and float(c["live_pct"]) >= 9.8:
            blockers.append(f"{sym}: limit-up")
            continue
        target_cny = cap * float(p.get("weight") or 0)
        lots, pos_cny = affordable_lots(price, target_cny)
        if lots < 1:
            blockers.append(f"{sym}: insufficient capital for 1 lot")
            continue
        positions.append({
            "symbol": sym,
            "name": c.get("name") or sym,
            "sector": c.get("sector") or p.get("sector") or "",
            "score": float(c.get("final_score") or c.get("score") or 0),
            "weight": float(p.get("weight") or 0),
            "lots": lots,
            "quantity": lots * 100,
            "reference_price": round(price, 2),
            "position_cny": pos_cny,
            "allocation_pct": round(pos_cny / cap * 100, 1) if cap else 0,
        })

    return {
        "capital_cny": cap,
        "max_holdings": max_k,
        "weights": opt.get("weights") or {},
        "positions": positions,
        "optimizer_notes": opt.get("notes") or [],
        "constraints": opt.get("constraints") or {},
        "blockers": blockers,
        "n_candidates_in": len(candidates),
        "n_positions": len(positions),
    }
