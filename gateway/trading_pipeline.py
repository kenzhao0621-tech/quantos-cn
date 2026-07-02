"""Screener → portfolio → paper/live execution pipeline."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from gateway.config import ROOT
from gateway.execution.preflight import execution_preflight
from gateway.preferences import load_preferences
from quant.portfolio.unified import build_portfolio_allocation
from quant.version import SCREENER_ENGINE


def run_screener_with_allocation(
    *,
    preset: str | None = None,
    top_n: int = 25,
    mode: str = "eod",
    capital_cny: float | None = None,
) -> dict[str, Any]:
    from quant.application.screener_service import get_screener_service
    from quant.regime import load_regime_from_warehouse

    pref = load_preferences()
    cap = float(capital_cny or pref.capital_cny)
    if mode.lower() in ("live", "realtime", "intraday"):
        from quant.application.live_market_service import ensure_live_quotes

        ensure_live_quotes(refresh=True, max_age_sec=90)
    svc = get_screener_service()
    screen = svc.screen(
        preset=preset or pref.strategy_preset,
        top_n=max(25, min(top_n, 100)),
        min_amount_cny=pref.min_amount_cny,
        mode=mode,
        preferred_sectors=pref.preferred_sectors,
        excluded_sectors=pref.excluded_sectors,
        capital_cny=cap,
        fast=mode.lower() not in ("live", "realtime", "intraday"),
    )
    payload = screen.to_dict()
    if screen.blocked:
        return {"ok": False, "blocked": True, "blocker_reason": screen.blocker_reason, "screen": payload}

    regime = load_regime_from_warehouse()
    allocation = build_portfolio_allocation(
        payload.get("candidates") or [],
        capital_cny=cap,
        max_holdings=pref.max_positions,
        regime=regime,
    )
    payload["portfolio_allocation"] = allocation
    return {"ok": True, "screen": payload, "allocation": allocation}


def execute_allocation_lines(
    allocation: dict[str, Any],
    *,
    user_id: str,
    unattended: bool = False,
    allow_drift_override: bool = True,
    source: str = "trading_pipeline",
) -> dict[str, Any]:
    """Execute each portfolio line via paper or live router."""
    mode = "unattended" if unattended else "live"
    pre = execution_preflight(mode=mode, unattended=unattended, allow_drift_override=allow_drift_override)
    if not pre["allowed"]:
        return {"ok": False, "blockers": pre["blockers"], "warnings": pre.get("warnings"), "preflight": pre}

    positions = allocation.get("positions") or []
    if not positions:
        return {"ok": False, "blockers": allocation.get("blockers") or ["NO_EXECUTABLE_POSITIONS"]}

    results: list[dict[str, Any]] = []
    blockers: list[str] = list(allocation.get("blockers") or [])

    if not unattended:
        from gateway.brokers.execution_router import execute_order

        for pos in positions:
            r = execute_order(
                symbol=pos["symbol"],
                name=pos.get("name") or "",
                side="BUY",
                quantity=int(pos["quantity"]),
                limit_price=float(pos["reference_price"]),
                user_id=user_id,
                user_confirmed=True,
                unattended=False,
                source=source,
            )
            results.append({"symbol": pos["symbol"], **r})
            if not r.get("ok"):
                blockers.append(f"{pos['symbol']}: {r.get('error', {}).get('message', 'failed')}")
        return {
            "ok": any(r.get("ok") for r in results),
            "mode": "live_manual",
            "results": results,
            "blockers": blockers,
            "warnings": pre.get("warnings"),
            "preflight": pre,
        }

    from gateway.brokers.execution_router import execute_order

    for pos in positions:
        r = execute_order(
            symbol=pos["symbol"],
            name=pos.get("name") or "",
            side="BUY",
            quantity=int(pos["quantity"]),
            limit_price=float(pos["reference_price"]),
            user_id=user_id,
            unattended=True,
            source=source,
        )
        results.append({"symbol": pos["symbol"], **r})
        if not r.get("ok"):
            blockers.append(f"{pos['symbol']}: {r.get('error', {}).get('message', 'failed')}")

    return {
        "ok": any(r.get("ok") for r in results),
        "mode": "unattended",
        "results": results,
        "blockers": blockers,
        "warnings": pre.get("warnings"),
        "preflight": pre,
    }


def execute_paper_allocation(
    allocation: dict[str, Any],
    *,
    user_id: str,
    paper_adapter: Any,
    strategy_id: str = "unified_portfolio",
) -> dict[str, Any]:
    """Submit paper orders using validated portfolio lines."""
    pre = execution_preflight(mode="paper")
    if not pre["allowed"]:
        return {"ok": False, "blockers": pre["blockers"], "preflight": pre}

    from gateway.risk.engine import OrderIntent

    positions = allocation.get("positions") or []
    run_id = str(uuid.uuid4())[:8]
    orders: list[dict[str, Any]] = []
    blockers: list[str] = []

    for pos in positions:
        intent = OrderIntent(
            client_order_id=str(uuid.uuid4()),
            run_id=run_id,
            strategy_id=strategy_id,
            model_id=SCREENER_ENGINE,
            symbol=pos["symbol"],
            side="BUY",
            quantity=int(pos["quantity"]),
            limit_price=float(pos["reference_price"]),
            notional_cny=float(pos.get("position_cny") or 0),
        )
        order = paper_adapter.submit(intent, data_fresh=True, market_price=float(pos["reference_price"]))
        od = order.to_dict()
        if od.get("state") == "FILLED":
            orders.append(od)
        else:
            blockers.append(f"{pos['symbol']}: {od.get('reject_reason') or od.get('state')}")

    return {
        "ok": bool(orders),
        "run_id": run_id,
        "orders": orders,
        "blockers": blockers,
        "preflight": pre,
    }


def execute_order_ticket(
    ticket_id: str,
    *,
    user_id: str,
    unattended: bool = True,
) -> dict[str, Any]:
    path = ROOT / "data" / "gateway" / "order_tickets" / f"{ticket_id}.json"
    if not path.exists():
        return {"ok": False, "blockers": ["TICKET_NOT_FOUND"]}
    ticket = json.loads(path.read_text(encoding="utf-8"))
    allocation = {
        "positions": [
            {
                "symbol": ln["symbol"],
                "name": ln.get("name") or "",
                "quantity": ln["quantity"],
                "reference_price": ln["reference_price"],
                "position_cny": ln.get("notional_cny"),
            }
            for ln in ticket.get("lines") or []
        ],
    }
    return execute_allocation_lines(
        allocation,
        user_id=user_id,
        unattended=unattended,
        source=f"ticket:{ticket_id}",
    )
