"""Persist paper broker state across gateway restarts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.brokers.base import BrokerAdapter, Fill, Order, OrderState, Position
from gateway.config import ROOT

STATE_PATH = ROOT / "data" / "gateway" / "paper_state.json"


def save_paper_state(broker: BrokerAdapter) -> dict[str, Any]:
    payload = {
        "cash_cny": broker.cash_cny,
        "orders": [o.to_dict() for o in broker.orders.values()],
        "fills": [f.to_dict() for f in broker.fills],
        "positions": [p.to_dict() for p in broker.positions.values()],
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_paper_state(broker: BrokerAdapter) -> bool:
    if not STATE_PATH.exists():
        return False
    raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    broker.cash_cny = float(raw.get("cash_cny", broker.cash_cny))
    broker.orders = {}
    for row in raw.get("orders", []):
        order = Order(
            client_order_id=row["client_order_id"],
            run_id=row["run_id"],
            strategy_id=row["strategy_id"],
            model_id=row["model_id"],
            symbol=row["symbol"],
            side=row["side"],
            quantity=int(row["quantity"]),
            limit_price=float(row["limit_price"]),
            broker=row.get("broker", "paper"),
            state=OrderState(row.get("state", "FILLED")),
            filled_qty=int(row.get("filled_qty", 0)),
            avg_fill_price=float(row.get("avg_fill_price", 0)),
            fees_cny=float(row.get("fees_cny", 0)),
            created_at=row.get("created_at", ""),
            reject_reason=row.get("reject_reason", ""),
        )
        broker.orders[order.client_order_id] = order
    broker.fills = [
        Fill(
            fill_id=f["fill_id"],
            client_order_id=f["client_order_id"],
            symbol=f["symbol"],
            side=f["side"],
            quantity=int(f["quantity"]),
            price=float(f["price"]),
            fees_cny=float(f["fees_cny"]),
            filled_at=f["filled_at"],
        )
        for f in raw.get("fills", [])
    ]
    broker.positions = {}
    for row in raw.get("positions", []):
        sym = row["symbol"]
        broker.positions[sym] = Position(
            symbol=sym,
            quantity=int(row["quantity"]),
            avg_cost=float(row["avg_cost"]),
            market_value=float(row["market_value"]),
            unrealized_pnl=float(row["unrealized_pnl"]),
            available_qty=int(row.get("available_qty", 0)),
        )
    return True


def mark_paper_to_market(broker: BrokerAdapter) -> dict[str, float]:
    """Refresh position market values from canonical DuckDB closes."""
    prices: dict[str, float] = {}
    warehouse = ROOT / "data" / "warehouse" / "quant.duckdb"
    if not warehouse.exists() or not broker.positions:
        return prices
    try:
        import duckdb

        syms = list(broker.positions.keys())
        placeholders = ",".join(["?"] * len(syms))
        con = duckdb.connect(str(warehouse), read_only=True)
        rows = con.execute(
            f"""
            SELECT ts_code, close FROM (
                SELECT ts_code, close,
                       row_number() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS rn
                FROM daily_bars WHERE ts_code IN ({placeholders})
            ) WHERE rn = 1
            """,
            syms,
        ).fetchall()
        con.close()
        prices = {str(code): float(close) for code, close in rows if close}
    except Exception:
        prices = {}
    for sym, pos in broker.positions.items():
        px = prices.get(sym, pos.avg_cost)
        pos.market_value = round(px * pos.quantity, 2)
        pos.unrealized_pnl = round((px - pos.avg_cost) * pos.quantity, 2)
    return prices
