"""Shadow execution bridge — zero portfolio mutation."""

from __future__ import annotations

from typing import Any

from gateway.brokers.shadow import ShadowBrokerAdapter
from gateway.risk.engine import OrderIntent as GatewayOrderIntent, RiskEngine
from integrations.vnpy.event_bridge import EventBridge
from integrations.vnpy.order_intent import OrderIntent
from integrations.vnpy.risk_bridge import VnpyRiskBridge


class ShadowBridge:
    def __init__(
        self,
        risk_engine: RiskEngine | None = None,
        event_bridge: EventBridge | None = None,
    ) -> None:
        self.risk_bridge = VnpyRiskBridge(risk_engine)
        self.broker = ShadowBrokerAdapter(self.risk_bridge.risk)
        self.events = event_bridge or EventBridge()

    def submit(self, intent: OrderIntent, *, data_fresh: bool = True) -> dict[str, Any]:
        decision = self.risk_bridge.evaluate(intent, data_fresh=data_fresh, mode="SHADOW_LIVE")
        if not decision.approved:
            return {"status": "REJECTED", "risk": decision.to_dict(), "shadow_only": True}

        gw_intent = GatewayOrderIntent(
            client_order_id=intent.intent_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            notional_cny=intent.notional_cny(),
            run_id=intent.run_id,
        )
        order = self.broker.submit(gw_intent, data_fresh=data_fresh, market_price=intent.limit_price)
        self.events.emit_order(run_id=intent.run_id, order={**order.to_dict(), "shadow": True})
        return {"status": order.state.value, "order": order.to_dict(), "shadow_only": True}
