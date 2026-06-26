"""Safe Autopilot: research-to-order-ticket and optional unattended execution.

Generates auditable order tickets from ensemble screener + unified portfolio.
When live gates and preflight pass, tickets can be executed via
``gateway/trading_pipeline.execute_order_ticket`` (portal or API).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT
from gateway.preferences import UserPreferences, load_preferences

TICKET_DIR = ROOT / "data" / "gateway" / "order_tickets"


@dataclass
class OrderTicketLine:
    symbol: str
    side: str
    quantity: int
    reference_price: float
    notional_cny: float
    score: float
    sector: str = ""
    rationale: list[str] = field(default_factory=list)


@dataclass
class OrderTicket:
    ticket_id: str
    created_at: str
    mode: str
    preset: str
    status: str
    legal_boundary: str
    lines: list[OrderTicketLine]
    blockers: list[str] = field(default_factory=list)
    broker_handoff: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["lines"] = [asdict(x) for x in self.lines]
        return data


def readiness_snapshot() -> dict[str, Any]:
    from gateway.execution.preflight import execution_preflight
    from gateway.live_trading.gates import load_gates

    pref = load_preferences()
    gates = load_gates()
    pre_unattended = execution_preflight(mode="unattended", unattended=True, allow_drift_override=True)
    checks = [
        {"name": "legal_boundary", "passed": True, "detail": "真实交易须通过门控与券商确认路径"},
        {"name": "capital_configured", "passed": pref.capital_cny >= 1000, "detail": f"{pref.capital_cny:.0f} CNY"},
        {"name": "risk_profile", "passed": 0 < pref.max_loss_pct <= 0.5, "detail": f"max_loss_pct={pref.max_loss_pct:.2%}"},
        {"name": "position_limits", "passed": 1 <= pref.max_positions <= 30, "detail": f"max_positions={pref.max_positions}"},
        {"name": "platform_shadow_eligible", "passed": pre_unattended["closed_loop"].get("shadow_eligible", False), "detail": "闭环 shadow 门禁"},
        {"name": "unattended_gates", "passed": gates.unattended_auto_enabled and gates.execution_level >= 3, "detail": "CONDITIONAL_AUTO"},
    ]
    ready_auto = pre_unattended["allowed"] and gates.unattended_auto_enabled
    return {
        "ready_for_order_ticket": all(x["passed"] for x in checks[:4]),
        "ready_for_unattended_auto": ready_auto,
        "ready_for_real_auto_trade": ready_auto,
        "real_auto_trade_reason": None if ready_auto else (pre_unattended.get("blockers") or ["门控未就绪"])[0],
        "checks": checks,
        "preflight": pre_unattended,
        "preferences": pref.to_dict(),
    }


def generate_order_ticket(
    *,
    preset: str | None = None,
    top_n: int = 25,
    mode: str = "live",
) -> dict[str, Any]:
    from gateway.brokers.wizard import BROKER_PORTAL_LINKS
    from quant.application.screener_service import get_screener_service

    pref = load_preferences()
    preset = preset or pref.strategy_preset
    screen = get_screener_service().screen(
        preset=preset,
        top_n=max(25, min(top_n, 100)),
        min_amount_cny=pref.min_amount_cny,
        mode=mode,
        preferred_sectors=pref.preferred_sectors,
        excluded_sectors=pref.excluded_sectors,
    )
    if screen.blocked:
        ticket = OrderTicket(
            ticket_id=str(uuid.uuid4())[:8],
            created_at=datetime.now(timezone.utc).isoformat(),
            mode=mode,
            preset=preset,
            status="BLOCKED",
            legal_boundary="ORDER_TICKET_ONLY",
            lines=[],
            blockers=[screen.blocker_reason],
            broker_handoff=BROKER_PORTAL_LINKS,
        )
        return _persist_ticket(ticket)

    payload = screen.to_dict()
    allocation = payload.get("portfolio_allocation") or {}
    lines: list[OrderTicketLine] = []
    blockers: list[str] = list(allocation.get("blockers") or [])
    for pos in allocation.get("positions") or []:
        lines.append(OrderTicketLine(
            symbol=pos["symbol"],
            side="BUY",
            quantity=int(pos["quantity"]),
            reference_price=float(pos["reference_price"]),
            notional_cny=float(pos.get("position_cny") or 0),
            score=float(pos.get("score") or 0),
            sector=str(pos.get("sector") or ""),
            rationale=[f"ensemble score {pos.get('score')}", f"weight {pos.get('weight')}"],
        ))

    ticket = OrderTicket(
        ticket_id=str(uuid.uuid4())[:8],
        created_at=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        preset=preset,
        status="READY_FOR_MANUAL_CONFIRM" if lines else "NO_EXECUTABLE_LINES",
        legal_boundary="ORDER_TICKET_ONLY",
        lines=lines,
        blockers=blockers[:20],
        broker_handoff=BROKER_PORTAL_LINKS,
    )
    return _persist_ticket(ticket)


def _persist_ticket(ticket: OrderTicket) -> dict[str, Any]:
    TICKET_DIR.mkdir(parents=True, exist_ok=True)
    path = TICKET_DIR / f"{ticket.ticket_id}.json"
    data = ticket.to_dict()
    data["artifact_path"] = str(path.relative_to(ROOT))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data

