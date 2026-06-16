"""Paper execution bridge — Gateway PaperBroker + vn.py event semantics."""

from __future__ import annotations

from typing import Any, Optional

from gateway.brokers.paper import PaperBrokerAdapter
from gateway.risk.engine import OrderIntent as GatewayOrderIntent, RiskEngine
from integrations.vnpy.event_bridge import EventBridge
from integrations.vnpy.order_intent import OrderIntent
from integrations.vnpy.risk_bridge import VnpyRiskBridge


class PaperBridge:
    def __init__(
        self,
        risk_engine: RiskEngine | None = None,
        event_bridge: EventBridge | None = None,
    ) -> None:
        self.risk_bridge = VnpyRiskBridge(risk_engine)
        self.broker = PaperBrokerAdapter(self.risk_bridge.risk)
        self.events = event_bridge or EventBridge()

    def submit(self, intent: OrderIntent, *, data_fresh: bool = True) -> dict[str, Any]:
        decision = self.risk_bridge.evaluate(intent, data_fresh=data_fresh, mode="PAPER_TRADING")
        if not decision.approved:
            self.events.emit_order(run_id=intent.run_id, order={
                "intent_id": intent.intent_id, "state": "REJECTED", "reason": decision.reason,
            }, strategy_id=intent.strategy_id)
            return {"status": "REJECTED", "risk": decision.to_dict()}

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
        order = self.broker.submit(gw_intent, data_fresh=data_fresh, market_price=intent.limit_price)
        order_dict = order.to_dict()
        self.events.emit_order(run_id=intent.run_id, order=order_dict, strategy_id=intent.strategy_id)
        if order.state.value == "FILLED":
            self.events.emit_trade(run_id=intent.run_id, trade={
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "quantity": order.filled_qty,
                "price": order.avg_fill_price,
            }, strategy_id=intent.strategy_id)
        return {"status": order.state.value, "order": order_dict, "risk": decision.to_dict()}

    def pnl(self) -> dict[str, Any]:
        return self.broker.pnl_summary()

    def positions(self) -> list[dict[str, Any]]:
        return self.broker.list_positions()
