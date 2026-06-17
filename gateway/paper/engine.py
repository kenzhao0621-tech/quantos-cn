"""Paper trading engine — realistic A-share order state machine with event sourcing."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from gateway.config import ROOT
from gateway.risk.engine import OrderIntent, RiskEngine

EVENTS_PATH = ROOT / "data" / "gateway" / "paper_events.jsonl"
ORDERS_PATH = ROOT / "data" / "gateway" / "paper_orders.json"


class PaperOrderState(str, Enum):
    CREATED = "CREATED"
    RISK_REJECTED = "RISK_REJECTED"
    USER_CONFIRMATION_REQUIRED = "USER_CONFIRMATION_REQUIRED"
    PENDING_SUBMISSION = "PENDING_SUBMISSION"
    SUBMITTED = "SUBMITTED"
    BROKER_ACKNOWLEDGED = "BROKER_ACKNOWLEDGED"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN_REQUIRES_RECONCILIATION = "UNKNOWN_REQUIRES_RECONCILIATION"


TERMINAL = {
    PaperOrderState.FILLED,
    PaperOrderState.CANCELLED,
    PaperOrderState.REJECTED,
    PaperOrderState.EXPIRED,
    PaperOrderState.RISK_REJECTED,
}


@dataclass
class PaperOrder:
    order_id: str
    idempotency_key: str
    symbol: str
    side: str
    quantity: int
    limit_price: float
    state: PaperOrderState = PaperOrderState.CREATED
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    fees_cny: float = 0.0
    frozen_cash_cny: float = 0.0
    reject_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    run_id: str = ""
    strategy_id: str = ""
    model_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "state": self.state.value}


@dataclass
class PaperPosition:
    symbol: str
    quantity: int = 0
    sellable_qty: int = 0
    locked_qty: int = 0
    avg_cost: float = 0.0
    market_value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class PaperAccount:
    cash_available: float
    cash_frozen: float = 0.0
    positions: dict[str, PaperPosition] = field(default_factory=dict)

    @property
    def equity(self) -> float:
        return self.cash_available + self.cash_frozen + sum(p.market_value for p in self.positions.values())


class PaperTradingEngine:
    """Event-sourced paper broker with A-share constraints."""

    def __init__(self, risk: RiskEngine, *, capital_cny: float | None = None) -> None:
        self.risk = risk
        self.account = PaperAccount(cash_available=capital_cny or risk.config.capital.total_allocated_cny)
        self.orders: dict[str, PaperOrder] = {}
        self._idempotency: dict[str, str] = {}
        self._submitted_keys: set[str] = set()
        self._load_state()

    def _emit(self, order: PaperOrder, prev: PaperOrderState, reason: str, **extra: Any) -> None:
        order.updated_at = datetime.now(timezone.utc).isoformat()
        evt = {
            "event_id": str(uuid4()),
            "order_id": order.order_id,
            "idempotency_key": order.idempotency_key,
            "prev_state": prev.value,
            "new_state": order.state.value,
            "reason": reason,
            "timestamp": order.updated_at,
            **extra,
        }
        EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with EVENTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")
        self._persist()

    def _persist(self) -> None:
        ORDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "account": {
                "cash_available": self.account.cash_available,
                "cash_frozen": self.account.cash_frozen,
                "positions": {k: v.to_dict() for k, v in self.account.positions.items()},
            },
            "orders": {k: v.to_dict() for k, v in self.orders.items()},
            "idempotency": self._idempotency,
        }
        ORDERS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_state(self) -> None:
        if not ORDERS_PATH.exists():
            return
        try:
            raw = json.loads(ORDERS_PATH.read_text(encoding="utf-8"))
            acct = raw.get("account", {})
            self.account.cash_available = float(acct.get("cash_available", self.account.cash_available))
            self.account.cash_frozen = float(acct.get("cash_frozen", 0))
            for sym, p in acct.get("positions", {}).items():
                self.account.positions[sym] = PaperPosition(**p)
            for oid, o in raw.get("orders", {}).items():
                st = PaperOrderState(o.get("state", "CREATED"))
                self.orders[oid] = PaperOrder(
                    order_id=o["order_id"],
                    idempotency_key=o.get("idempotency_key", oid),
                    symbol=o["symbol"],
                    side=o["side"],
                    quantity=int(o["quantity"]),
                    limit_price=float(o["limit_price"]),
                    state=st,
                    filled_qty=int(o.get("filled_qty", 0)),
                    avg_fill_price=float(o.get("avg_fill_price", 0)),
                    fees_cny=float(o.get("fees_cny", 0)),
                    frozen_cash_cny=float(o.get("frozen_cash_cny", 0)),
                    reject_reason=o.get("reject_reason", ""),
                    created_at=o.get("created_at", ""),
                    updated_at=o.get("updated_at", ""),
                    run_id=o.get("run_id", ""),
                    strategy_id=o.get("strategy_id", ""),
                    model_id=o.get("model_id", ""),
                )
            self._idempotency = raw.get("idempotency", {})
        except Exception:
            pass

    def _validate_lot(self, side: str, quantity: int) -> str | None:
        if side == "BUY" and (quantity < 100 or quantity % 100 != 0):
            return "INVALID_LOT_BUY_100_SHARE"
        if side == "SELL" and quantity <= 0:
            return "INVALID_LOT_SELL"
        return None

    def _estimate_fees(self, side: str, notional: float) -> float:
        commission = max(5.0, notional * 0.00025)
        stamp = notional * 0.0005 if side == "SELL" else 0.0
        transfer = notional * 0.00001
        return round(commission + stamp + transfer, 2)

    def submit(
        self,
        intent: OrderIntent,
        *,
        data_fresh: bool = True,
        market_price: Optional[float] = None,
        limit_up_block: bool = False,
        suspended: bool = False,
        fill_ratio: float = 1.0,
        idempotency_key: str = "",
    ) -> PaperOrder:
        key = idempotency_key or intent.client_order_id or str(uuid4())
        if key in self._idempotency:
            return self.orders[self._idempotency[key]]

        order = PaperOrder(
            order_id=str(uuid4()),
            idempotency_key=key,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            run_id=intent.run_id,
            strategy_id=intent.strategy_id,
            model_id=intent.model_id,
        )
        prev = order.state
        self.orders[order.order_id] = order
        self._idempotency[key] = order.order_id

        lot_err = self._validate_lot(intent.side, intent.quantity)
        if lot_err:
            order.state = PaperOrderState.REJECTED
            order.reject_reason = lot_err
            self._emit(order, prev, lot_err)
            return order

        if suspended:
            order.state = PaperOrderState.REJECTED
            order.reject_reason = "SUSPENDED"
            self._emit(order, prev, "SUSPENDED")
            return order

        if limit_up_block and intent.side == "BUY":
            order.state = PaperOrderState.REJECTED
            order.reject_reason = "LIMIT_UP_NO_ENTRY"
            self._emit(order, prev, "LIMIT_UP_NO_ENTRY")
            return order

        decision = self.risk.evaluate_intent(intent, data_fresh=data_fresh)
        if not decision.approved:
            order.state = PaperOrderState.RISK_REJECTED
            order.reject_reason = decision.reason
            self._emit(order, prev, decision.reason)
            return order

        notional = intent.limit_price * intent.quantity
        fees = self._estimate_fees(intent.side, notional)
        if intent.side == "BUY":
            required = notional + fees
            if required > self.account.cash_available:
                order.state = PaperOrderState.REJECTED
                order.reject_reason = "INSUFFICIENT_CASH"
                self._emit(order, prev, "INSUFFICIENT_CASH", required=required, available=self.account.cash_available)
                return order
            self.account.cash_available -= required
            self.account.cash_frozen += required
            order.frozen_cash_cny = required

        if intent.side == "SELL":
            pos = self.account.positions.get(intent.symbol)
            if not pos or pos.sellable_qty < intent.quantity:
                order.state = PaperOrderState.REJECTED
                order.reject_reason = "T_PLUS_1_SELLABLE_INSUFFICIENT"
                self._emit(order, prev, "T_PLUS_1_SELLABLE_INSUFFICIENT")
                return order

        for st in (PaperOrderState.PENDING_SUBMISSION, PaperOrderState.SUBMITTED, PaperOrderState.BROKER_ACKNOWLEDGED, PaperOrderState.ACCEPTED):
            prev = order.state
            order.state = st
            self._emit(order, prev, f"transition_{st.value}")

        fill_price = market_price or intent.limit_price
        fill_qty = int(intent.quantity * max(0.0, min(1.0, fill_ratio)))
        if fill_qty <= 0:
            order.state = PaperOrderState.REJECTED
            order.reject_reason = "NO_FILL"
            self._emit(order, prev, "NO_FILL")
            if order.frozen_cash_cny:
                self.account.cash_frozen -= order.frozen_cash_cny
                self.account.cash_available += order.frozen_cash_cny
                order.frozen_cash_cny = 0
            return order

        if fill_qty < intent.quantity:
            order.state = PaperOrderState.PARTIALLY_FILLED
            prev = order.state
            self._emit(order, prev, "partial_fill", fill_qty=fill_qty)

        actual_fees = self._estimate_fees(intent.side, fill_price * fill_qty)
        order.filled_qty = fill_qty
        order.avg_fill_price = fill_price
        order.fees_cny = actual_fees
        prev = order.state
        order.state = PaperOrderState.FILLED
        self._apply_fill(order, fill_price, actual_fees)
        self._emit(order, prev, "filled", fill_qty=fill_qty, price=fill_price, fees=actual_fees)
        self.risk.on_order_accepted()
        self._submitted_keys.add(key)
        return order

    def _apply_fill(self, order: PaperOrder, price: float, fees: float) -> None:
        if order.side == "BUY":
            if order.frozen_cash_cny:
                refund = order.frozen_cash_cny - (price * order.filled_qty + fees)
                self.account.cash_frozen -= order.frozen_cash_cny
                self.account.cash_available += max(0, refund)
                order.frozen_cash_cny = 0
            pos = self.account.positions.get(order.symbol)
            if pos:
                total = pos.quantity + order.filled_qty
                pos.avg_cost = (pos.avg_cost * pos.quantity + price * order.filled_qty) / total
                pos.quantity = total
                pos.locked_qty += order.filled_qty
                pos.market_value = pos.quantity * price
            else:
                self.account.positions[order.symbol] = PaperPosition(
                    symbol=order.symbol,
                    quantity=order.filled_qty,
                    sellable_qty=0,
                    locked_qty=order.filled_qty,
                    avg_cost=price,
                    market_value=price * order.filled_qty,
                )
        else:
            pos = self.account.positions[order.symbol]
            proceeds = price * order.filled_qty - fees
            self.account.cash_available += proceeds
            pos.quantity -= order.filled_qty
            pos.sellable_qty -= order.filled_qty
            pos.market_value = pos.quantity * price
            if pos.quantity <= 0:
                del self.account.positions[order.symbol]

    def settle_t_plus_1(self, symbol: str) -> None:
        """Move locked quantity to sellable (call at next session open)."""
        pos = self.account.positions.get(symbol)
        if pos:
            pos.sellable_qty += pos.locked_qty
            pos.locked_qty = 0

    def list_orders(self) -> list[dict[str, Any]]:
        return [o.to_dict() for o in self.orders.values()]

    def account_summary(self) -> dict[str, Any]:
        return {
            "cash_available": round(self.account.cash_available, 2),
            "cash_frozen": round(self.account.cash_frozen, 2),
            "equity_cny": round(self.account.equity, 2),
            "positions": [p.to_dict() for p in self.account.positions.values()],
            "open_orders": sum(1 for o in self.orders.values() if o.state not in TERMINAL),
        }
