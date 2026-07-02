"""Tradability-first masking for A-share universe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TradabilityMask:
    valid_for_research: bool
    valid_for_factor: bool
    valid_for_ranking: bool
    valid_for_purchase: bool
    valid_for_sale: bool
    status: str
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid_for_research": self.valid_for_research,
            "valid_for_factor": self.valid_for_factor,
            "valid_for_ranking": self.valid_for_ranking,
            "valid_for_purchase": self.valid_for_purchase,
            "valid_for_sale": self.valid_for_sale,
            "tradability_status": self.status,
            "tradability_blockers": list(self.blockers),
        }


def board_limit_pct(symbol: str, *, is_st: bool = False) -> float:
    """Per-board price limit (%): STAR/ChiNext 20, BSE 30, ST 5, main 10."""
    code = symbol.split(".")[0] if symbol else ""
    if code.startswith(("688", "689")):
        return 20.0
    if code.startswith(("300", "301", "302")):
        return 20.0
    if code.startswith(("4", "8")) or symbol.upper().endswith(".BJ"):
        return 30.0
    return 5.0 if is_st else 10.0


def evaluate_tradability(
    *,
    symbol: str,
    last_close: float,
    last_pct: float,
    avg_amount: float,
    min_amount_cny: float = 5e7,
    capital_cny: float = 5000.0,
    is_st: bool = False,
    suspended: bool = False,
) -> TradabilityMask:
    blockers: list[str] = []
    if suspended:
        blockers.append("SUSPENDED")
    if is_st or (symbol and ("ST" in symbol.upper() or symbol.startswith("8") or symbol.startswith("4"))):
        blockers.append("ST_OR_RISKY_BOARD")
    limit = board_limit_pct(symbol, is_st=is_st)
    if last_pct >= limit - 0.2:
        blockers.append("LIMIT_UP_NO_ENTRY")
    if last_pct <= -(limit - 0.2):
        blockers.append("LIMIT_DOWN")
    if avg_amount < min_amount_cny:
        blockers.append("LOW_LIQUIDITY")
    lot_cost = last_close * 100
    if lot_cost + _est_fees(lot_cost) > capital_cny:
        blockers.append("UNAFFORDABLE_LOT")
    if last_close <= 0:
        blockers.append("INVALID_PRICE")

    purchase_ok = not any(b in blockers for b in (
        "SUSPENDED", "LIMIT_UP_NO_ENTRY", "LOW_LIQUIDITY", "UNAFFORDABLE_LOT", "INVALID_PRICE"
    ))
    ranking_ok = "INVALID_PRICE" not in blockers and "SUSPENDED" not in blockers
    return TradabilityMask(
        valid_for_research=True,
        valid_for_factor=ranking_ok,
        valid_for_ranking=ranking_ok,
        valid_for_purchase=purchase_ok,
        valid_for_sale=not suspended and last_close > 0,
        status="TRADABLE" if purchase_ok else ("WATCH_ONLY" if ranking_ok else "BLOCKED"),
        blockers=tuple(blockers),
    )


def _est_fees(notional: float) -> float:
    commission = max(notional * 0.00025, 5.0)
    return commission
