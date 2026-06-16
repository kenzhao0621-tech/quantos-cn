"""Position and account reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ReconciliationReport:
    ok: bool
    local_positions: list[dict[str, Any]] = field(default_factory=list)
    broker_positions: list[dict[str, Any]] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)
    unknown_orders: list[str] = field(default_factory=list)
    action: str = "OK"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "local_positions": self.local_positions,
            "broker_positions": self.broker_positions,
            "mismatches": self.mismatches,
            "unknown_orders": self.unknown_orders,
            "action": self.action,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


def reconcile(
    local_positions: list[dict[str, Any]],
    broker_positions: list[dict[str, Any]] | None = None,
    unknown_order_ids: list[str] | None = None,
) -> ReconciliationReport:
    broker_positions = broker_positions or []
    unknown_order_ids = unknown_order_ids or []
    mismatches: list[str] = []
    local_map = {p.get("symbol"): p.get("quantity", 0) for p in local_positions}
    broker_map = {p.get("symbol"): p.get("quantity", 0) for p in broker_positions}
    for sym, qty in local_map.items():
        if sym in broker_map and broker_map[sym] != qty:
            mismatches.append(f"qty_mismatch:{sym}")
    action = "OK"
    if unknown_order_ids:
        action = "HALT_AND_RECONCILE"
    elif mismatches:
        action = "RECONCILE_REQUIRED"
    ok = action == "OK" and not unknown_order_ids
    return ReconciliationReport(
        ok=ok,
        local_positions=local_positions,
        broker_positions=broker_positions,
        mismatches=mismatches,
        unknown_orders=unknown_order_ids,
        action=action,
    )
