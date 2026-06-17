"""Unified BrokerGateway — adapter registry for paper, QMT, PTrade (sandbox)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from gateway.brokers.base import Order, OrderState


class BrokerHealth(str, Enum):
    READY = "READY"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DISCONNECTED = "DISCONNECTED"
    SANDBOX = "SANDBOX"


@dataclass
class BrokerEvent:
    event_type: str
    payload: dict[str, Any]
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BrokerGatewayAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def connect(self) -> dict[str, Any]: ...

    @abstractmethod
    def health(self) -> dict[str, Any]: ...

    @abstractmethod
    def place_order(self, order: dict[str, Any]) -> dict[str, Any]: ...

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        return {"ok": False, "reason": "not_supported"}

    def get_orders(self) -> list[dict[str, Any]]:
        return []

    def get_trades(self) -> list[dict[str, Any]]:
        return []


class PaperGatewayAdapter(BrokerGatewayAdapter):
    name = "PaperGateway"

    def __init__(self, paper_broker: Any) -> None:
        self._broker = paper_broker

    def connect(self) -> dict[str, Any]:
        return {"ok": True, "health": BrokerHealth.READY.value, "real_orders": False}

    def health(self) -> dict[str, Any]:
        return {"status": BrokerHealth.READY.value, "broker": self.name, "real_orders": False}

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        from gateway.risk.engine import OrderIntent
        intent = OrderIntent(
            client_order_id=order.get("client_order_id") or str(uuid.uuid4()),
            symbol=order["symbol"],
            side=order.get("side", "BUY"),
            quantity=int(order["quantity"]),
            limit_price=float(order.get("limit_price") or order.get("price") or 0),
            notional_cny=float(order.get("notional_cny") or 0),
            run_id=order.get("run_id", ""),
            strategy_id=order.get("strategy_id", ""),
            model_id=order.get("model_id", ""),
        )
        result = self._broker.submit(intent, data_fresh=True, market_price=intent.limit_price)
        return {"ok": result.state != OrderState.REJECTED, "order": result.to_dict()}


class QMTSandboxAdapter(BrokerGatewayAdapter):
    name = "QMTGateway"

    def connect(self) -> dict[str, Any]:
        from gateway.brokers.connection_manager import load_broker_config, test_broker_connection
        cfg = load_broker_config()
        conn = test_broker_connection(cfg)
        real = bool(conn.get("real_orders"))
        return {
            "ok": conn.get("connected", False),
            "health": BrokerHealth.READY.value if conn.get("connected") else BrokerHealth.NOT_CONFIGURED.value,
            "handoff": conn.get("handoff", "qmt_csv_drop"),
            "real_orders": real,
            "message": conn.get("message"),
        }

    def health(self) -> dict[str, Any]:
        c = self.connect()
        return {
            "status": c.get("health"),
            "broker": self.name,
            "message": c.get("message") or "xtquant 或 CSV 路径",
            "real_orders": c.get("real_orders", False),
        }

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        from gateway.brokers.unified_bridge import place_real_order
        return place_real_order(
            symbol=order["symbol"],
            name=order.get("name", ""),
            side=order.get("side", "BUY"),
            quantity=int(order["quantity"]),
            limit_price=float(order.get("limit_price") or order.get("price") or 0),
            user_confirmed=bool(order.get("user_confirmed")),
            user_id=order.get("user_id", "default"),
            source=order.get("source", "gateway"),
        )


class PTradeSandboxAdapter(BrokerGatewayAdapter):
    name = "PTradeGateway"

    def connect(self) -> dict[str, Any]:
        return {"ok": False, "health": BrokerHealth.NOT_CONFIGURED.value, "real_orders": False}

    def health(self) -> dict[str, Any]:
        return {
            "status": BrokerHealth.NOT_CONFIGURED.value,
            "broker": self.name,
            "message": "PTrade 需券商授权 — LEGAL_REVIEW_REQUIRED",
        }

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": False,
            "reason": "NOT_CONFIGURED",
            "legal_boundary": "LEGAL_REVIEW_REQUIRED",
            "order_draft": order,
        }


class BrokerGateway:
    """Facade selecting adapter by broker id."""

    def __init__(self, adapters: dict[str, BrokerGatewayAdapter] | None = None) -> None:
        self._adapters = adapters or {}

    def register(self, broker_id: str, adapter: BrokerGatewayAdapter) -> None:
        self._adapters[broker_id] = adapter

    def get(self, broker_id: str) -> BrokerGatewayAdapter | None:
        return self._adapters.get(broker_id)

    def health_all(self) -> list[dict[str, Any]]:
        return [a.health() for a in self._adapters.values()]

    def connect(self, broker_id: str) -> dict[str, Any]:
        adapter = self.get(broker_id)
        if not adapter:
            return {"ok": False, "reason": "unknown_broker"}
        return adapter.connect()


def build_default_gateway(paper_broker: Any) -> BrokerGateway:
    gw = BrokerGateway()
    gw.register("paper", PaperGatewayAdapter(paper_broker))
    gw.register("qmt_local", QMTSandboxAdapter())
    gw.register("ptrade", PTradeSandboxAdapter())
    return gw
