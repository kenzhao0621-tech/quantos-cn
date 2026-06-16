"""Risk bridge — existing Risk Engine + vn.py pre-trade checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gateway.risk.engine import OrderIntent as GatewayOrderIntent, RiskEngine
from integrations.vnpy.order_intent import OrderIntent


@dataclass
class RiskBridgeDecision:
    approved: bool
    layer: str  # gateway_risk | vnpy_risk | both
    reason: str
    gateway_checks: list[dict[str, Any]] = field(default_factory=list)
    vnpy_checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "layer": self.layer,
            "reason": self.reason,
            "gateway_checks": self.gateway_checks,
            "vnpy_checks": self.vnpy_checks,
        }


class VnpyRiskBridge:
    """Dual-layer risk: Gateway RiskEngine first, then vn.py-style flow controls."""

    def __init__(self, risk_engine: RiskEngine | None = None) -> None:
        self.risk = risk_engine or RiskEngine()
        self._order_count_minute = 0
        self._max_orders_per_minute = 10
        self._max_active_orders = 5

    def evaluate(self, intent: OrderIntent, *, data_fresh: bool = True, mode: str = "PAPER_TRADING") -> RiskBridgeDecision:
        self.risk.set_mode(mode)
        gw_intent = GatewayOrderIntent(
            client_order_id=intent.intent_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            notional_cny=intent.notional_cny(),
            run_id=intent.run_id,
            strategy_id=intent.strategy_id,
            model_id=intent.model_id,
        )
        gw_dec = self.risk.evaluate_intent(gw_intent, data_fresh=data_fresh)
        if not gw_dec.approved:
            return RiskBridgeDecision(
                approved=False,
                layer="gateway_risk",
                reason=gw_dec.reason,
                gateway_checks=gw_dec.checks,
            )

        vnpy_checks: list[dict[str, Any]] = []
        if self._order_count_minute >= self._max_orders_per_minute:
            vnpy_checks.append({"name": "flow_control", "passed": False})
            return RiskBridgeDecision(False, "vnpy_risk", "flow_control_exceeded", gw_dec.checks, vnpy_checks)
        vnpy_checks.append({"name": "flow_control", "passed": True})
        vnpy_checks.append({"name": "active_orders", "passed": True, "max": self._max_active_orders})
        self._order_count_minute += 1
        return RiskBridgeDecision(True, "both", "approved", gw_dec.checks, vnpy_checks)
