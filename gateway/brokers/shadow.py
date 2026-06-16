"""Shadow broker — logs hypothetical orders without portfolio mutation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from gateway.brokers.base import BrokerAdapter, Order, OrderState
from gateway.config import ROOT
from gateway.risk.engine import OrderIntent


class ShadowBrokerAdapter(BrokerAdapter):
    broker_name = "shadow"

    def __init__(self, risk_engine, log_path: Path | None = None) -> None:
        super().__init__(risk_engine)
        self.log_path = log_path or ROOT / "data" / "gateway" / "shadow_orders.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def submit(
        self,
        intent: OrderIntent,
        *,
        data_fresh: bool = True,
        market_price: Optional[float] = None,
    ) -> Order:
        decision = self.risk.evaluate_intent(intent, data_fresh=data_fresh)
        order = Order(
            client_order_id=intent.client_order_id,
            run_id=intent.run_id,
            strategy_id=intent.strategy_id,
            model_id=intent.model_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            broker=self.broker_name,
        )
        if not decision.approved:
            order.state = OrderState.REJECTED
            order.reject_reason = decision.reason
        else:
            order.state = OrderState.FILLED
            order.filled_qty = intent.quantity
            order.avg_fill_price = market_price or intent.limit_price
            self._append_shadow_log(order, market_price)
        self.orders[order.client_order_id] = order
        return order

    def _append_shadow_log(self, order: Order, market_price: Optional[float]) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "order": order.to_dict(),
            "hypothetical_market_price": market_price,
            "note": "shadow_only_no_portfolio_mutation",
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def list_orders(self) -> list[dict[str, Any]]:
        return super().list_orders()
