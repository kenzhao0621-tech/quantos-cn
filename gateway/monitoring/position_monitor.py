"""Intraday position monitor — mark paper/shadow/ticket lines to latest prices."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from gateway.config import ROOT

logger = logging.getLogger(__name__)

WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"
LIVE_SNAPSHOT = ROOT / "data" / "gateway" / "live_snapshot.json"
TICKET_DIR = ROOT / "data" / "gateway" / "order_tickets"


def _live_prices() -> dict[str, float]:
    try:
        from quant.application.live_market_service import live_price_map

        prices = live_price_map()
        if prices:
            return prices
    except Exception as exc:
        logger.warning("position_monitor: live price map unavailable, falling back to EOD: %s", exc)
    prices: dict[str, float] = {}
    if WAREHOUSE.exists():
        try:
            import duckdb

            con = duckdb.connect(str(WAREHOUSE), read_only=True)
            rows = con.execute(
                "SELECT ts_code, close FROM daily_bars WHERE trade_date = (SELECT MAX(trade_date) FROM daily_bars)"
            ).fetchall()
            con.close()
            for sym, close in rows:
                if sym not in prices and close:
                    prices[str(sym)] = float(close)
        except Exception as exc:
            logger.warning("position_monitor: EOD price fallback failed: %s", exc)
    return prices


def build_position_monitor(*, paper: Any, shadow_events: list[dict] | None = None) -> dict[str, Any]:
    prices = _live_prices()
    positions: list[dict[str, Any]] = []
    for sym, pos in getattr(paper, "positions", {}).items():
        qty = int(getattr(pos, "quantity", 0) or getattr(pos, "qty", 0))
        cost = float(getattr(pos, "avg_cost", 0) or getattr(pos, "cost", 0))
        px = prices.get(sym, cost)
        mv = qty * px
        pnl = (px - cost) * qty if cost else 0.0
        positions.append({
            "symbol": sym,
            "quantity": qty,
            "cost": round(cost, 3),
            "last_price": round(px, 3),
            "market_value": round(mv, 2),
            "unrealized_pnl": round(pnl, 2),
            "source": "paper",
        })

    latest_ticket = None
    ticket_lines: list[dict[str, Any]] = []
    if TICKET_DIR.exists():
        paths = sorted(TICKET_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if paths:
            latest_ticket = json.loads(paths[0].read_text(encoding="utf-8"))
            for ln in latest_ticket.get("lines", []):
                sym = ln.get("symbol")
                ref = float(ln.get("reference_price", 0))
                px = prices.get(sym, ref)
                ticket_lines.append({
                    **ln,
                    "last_price": round(px, 3),
                    "price_drift_pct": round((px / ref - 1) * 100, 2) if ref else 0,
                })

    return {
        "price_source_count": len(prices),
        "paper_positions": positions,
        "paper_equity_estimate": round(
            float(getattr(paper, "cash_cny", 0)) + sum(p["market_value"] for p in positions), 2
        ),
        "latest_ticket_id": latest_ticket.get("ticket_id") if latest_ticket else None,
        "latest_ticket_status": latest_ticket.get("status") if latest_ticket else None,
        "ticket_lines_live": ticket_lines,
        "shadow_recent": (shadow_events or [])[-5:],
    }
