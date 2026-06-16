"""Gateway registry — Paper, Shadow, ReadOnly, ManualConfirm, broker stubs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from integrations.vnpy.order_intent import OrderIntent


class GatewayKind(str, Enum):
    PAPER = "PaperGateway"
    SHADOW = "ShadowGateway"
    READONLY = "ReadOnlyGateway"
    MANUAL_CONFIRM = "ManualConfirmGateway"
    XTP = "XTPGateway"
    TORA = "TORAGateway"
    QMT = "QMTGateway"
    PTRADE = "PTradeGateway"


@dataclass
class GatewaySpec:
    name: str
    kind: GatewayKind
    enabled: bool
    configured: bool
    auto_execute: bool
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "enabled": self.enabled,
            "configured": self.configured,
            "auto_execute": self.auto_execute,
            "description": self.description,
        }


class GatewayRegistry:
    """Unified broker gateway registry — live gateways disabled by default."""

    def __init__(self) -> None:
        self._gateways: dict[str, GatewaySpec] = {
            "PaperGateway": GatewaySpec(
                "PaperGateway", GatewayKind.PAPER, True, True, True,
                "Local simulated A-share execution",
            ),
            "ShadowGateway": GatewaySpec(
                "ShadowGateway", GatewayKind.SHADOW, True, True, True,
                "Hypothetical orders — no portfolio mutation",
            ),
            "ReadOnlyGateway": GatewaySpec(
                "ReadOnlyGateway", GatewayKind.READONLY, True, True, False,
                "Broker read-only sync — no orders",
            ),
            "ManualConfirmGateway": GatewaySpec(
                "ManualConfirmGateway", GatewayKind.MANUAL_CONFIRM, True, True, False,
                "Real execution requires human confirmation — max mode without broker API",
            ),
            "XTPGateway": GatewaySpec(
                "XTPGateway", GatewayKind.XTP, False, False, False,
                "XTP — requires authorized credentials",
            ),
            "QMTGateway": GatewaySpec(
                "QMTGateway", GatewayKind.QMT, False, False, False,
                "MiniQMT — requires authorized credentials",
            ),
        }
        self._active = "PaperGateway"

    def list_gateways(self) -> list[dict[str, Any]]:
        return [g.to_dict() for g in self._gateways.values()]

    def get(self, name: str) -> Optional[GatewaySpec]:
        return self._gateways.get(name)

    def set_active(self, name: str) -> tuple[bool, str]:
        g = self._gateways.get(name)
        if not g or not g.enabled:
            return False, "gateway_not_available"
        if g.kind not in (GatewayKind.PAPER, GatewayKind.SHADOW) and not g.configured:
            return False, "gateway_not_configured"
        self._active = name
        return True, "ok"

    @property
    def active(self) -> str:
        return self._active

    def route_intent(self, intent: OrderIntent) -> dict[str, Any]:
        g = self._gateways[self._active]
        if not g.auto_execute and g.kind == GatewayKind.MANUAL_CONFIRM:
            return {
                "routed_to": g.name,
                "status": "PENDING_MANUAL_CONFIRM",
                "intent": intent.to_dict(),
                "note": "REAL_EXECUTION=MANUAL_CONFIRM_ONLY",
            }
        if g.kind in (GatewayKind.XTP, GatewayKind.QMT, GatewayKind.TORA) and not g.configured:
            return {"routed_to": g.name, "status": "REJECTED", "reason": "broker_not_configured"}
        return {"routed_to": g.name, "status": "ROUTED", "intent": intent.to_dict()}
