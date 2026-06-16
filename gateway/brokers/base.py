"""Broker adapter base and order state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from gateway import PAPER_TRADING_ONLY, REAL_MONEY_EXECUTION_DISABLED
from gateway.risk.engine import OrderIntent, RiskEngine


class OrderState(str, Enum):
    CREATED = "CREATED"
    RISK_APPROVED = "RISK_APPROVED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


@dataclass
class Order:
    client_order_id: str
    run_id: str
    strategy_id: str
    model_id: str
    symbol: str
    side: str
    quantity: int
    limit_price: float
    state: OrderState = OrderState.CREATED
    broker: str = "paper"
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    fees_cny: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reject_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "run_id": self.run_id,
            "strategy_id": self.strategy_id,
            "model_id": self.model_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "state": self.state.value,
            "broker": self.broker,
            "filled_qty": self.filled_qty,
            "avg_fill_price": self.avg_fill_price,
            "fees_cny": self.fees_cny,
            "created_at": self.created_at,
            "reject_reason": self.reject_reason,
        }


@dataclass
class Fill:
    fill_id: str
    client_order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    fees_cny: float
    filled_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "fees_cny": self.fees_cny,
            "filled_at": self.filled_at,
        }


@dataclass
class Position:
    symbol: str
    quantity: int
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    available_qty: int  # T+1

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "available_qty": self.available_qty,
        }


class BrokerAdapter:
    broker_name: str = "base"

    def __init__(self, risk_engine: RiskEngine) -> None:
        if not PAPER_TRADING_ONLY or not REAL_MONEY_EXECUTION_DISABLED:
            raise RuntimeError("real-money execution disabled in this batch")
        self.risk = risk_engine
        self.orders: dict[str, Order] = {}
        self.fills: list[Fill] = []
        self.positions: dict[str, Position] = {}
        self.cash_cny = risk_engine.config.capital.total_allocated_cny

    def submit(
        self,
        intent: OrderIntent,
        *,
        data_fresh: bool = True,
        market_price: Optional[float] = None,
    ) -> Order:
        order = Order(
            client_order_id=intent.client_order_id or str(uuid4()),
            run_id=intent.run_id,
            strategy_id=intent.strategy_id,
            model_id=intent.model_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            broker=self.broker_name,
        )
        decision = self.risk.evaluate_intent(intent, data_fresh=data_fresh)
        if not decision.approved:
            order.state = OrderState.REJECTED
            order.reject_reason = decision.reason
            self.orders[order.client_order_id] = order
            return order
        order.state = OrderState.RISK_APPROVED
        order.state = OrderState.SUBMITTED
        order.state = OrderState.ACKNOWLEDGED
        fill_price = market_price or intent.limit_price
        fees = self._calc_fees(intent.side, fill_price * intent.quantity)
        order.filled_qty = intent.quantity
        order.avg_fill_price = fill_price
        order.fees_cny = fees
        order.state = OrderState.FILLED
        self.orders[order.client_order_id] = order
        self.fills.append(Fill(
            fill_id=str(uuid4()),
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            fees_cny=fees,
            filled_at=datetime.now(timezone.utc).isoformat(),
        ))
        self._update_position(order, fill_price, fees)
        self.risk.on_order_accepted()
        return order

    def _calc_fees(self, side: str, notional: float) -> float:
        commission = max(5.0, notional * 0.00025)
        stamp = notional * 0.0005 if side == "SELL" else 0.0
        transfer = notional * 0.00001
        return round(commission + stamp + transfer, 2)

    def _update_position(self, order: Order, fill_price: float, fees: float) -> None:
        pos = self.positions.get(order.symbol)
        if order.side == "BUY":
            self.cash_cny -= fill_price * order.quantity + fees
            if pos:
                total_qty = pos.quantity + order.quantity
                avg = ((pos.avg_cost * pos.quantity) + fill_price * order.quantity) / total_qty
                pos.quantity = total_qty
                pos.avg_cost = avg
                pos.available_qty = pos.quantity  # simplified T+0 buy, T+1 sell availability
            else:
                self.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    avg_cost=fill_price,
                    market_value=fill_price * order.quantity,
                    unrealized_pnl=0.0,
                    available_qty=0,
                )
        else:
            if not pos or pos.available_qty < order.quantity:
                order.state = OrderState.REJECTED
                order.reject_reason = "insufficient_available_qty_t_plus_1"
                return
            self.cash_cny += fill_price * order.quantity - fees
            pos.quantity -= order.quantity
            pos.available_qty -= order.quantity
            if pos.quantity == 0:
                del self.positions[order.symbol]

    def list_orders(self) -> list[dict[str, Any]]:
        return [o.to_dict() for o in self.orders.values()]

    def list_fills(self) -> list[dict[str, Any]]:
        return [f.to_dict() for f in self.fills]

    def list_positions(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.positions.values()]

    def pnl_summary(self) -> dict[str, Any]:
        equity = self.cash_cny + sum(p.market_value for p in self.positions.values())
        start = self.risk.config.capital.total_allocated_cny
        return {
            "cash_cny": round(self.cash_cny, 2),
            "equity_cny": round(equity, 2),
            "realized_pnl_cny": round(equity - start, 2),
            "open_positions": len(self.positions),
        }
