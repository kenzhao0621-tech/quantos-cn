"""Safe Autopilot: automated research-to-order-ticket workflow.

This module deliberately stops at order tickets and broker handoff. It does not
send real-money orders. The goal is a production-quality workflow that is
auditable, explainable, and compatible with official broker confirmation flows.
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
    pref = load_preferences()
    checks = [
        {"name": "legal_boundary", "passed": True, "detail": "真实交易必须用户本人在官方券商平台确认"},
        {"name": "capital_configured", "passed": pref.capital_cny >= 1000, "detail": f"{pref.capital_cny:.0f} CNY"},
        {"name": "risk_profile", "passed": 0 < pref.max_loss_pct <= 0.5, "detail": f"max_loss_pct={pref.max_loss_pct:.2%}"},
        {"name": "position_limits", "passed": 1 <= pref.max_positions <= 30, "detail": f"max_positions={pref.max_positions}"},
        {"name": "broker_handoff", "passed": True, "detail": "官方链接/本地客户端/人工确认路径可用"},
    ]
    return {
        "ready_for_order_ticket": all(x["passed"] for x in checks),
        "ready_for_real_auto_trade": False,
        "real_auto_trade_reason": "不支持绕过券商确认的全自动真实下单",
        "checks": checks,
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

    investable = pref.capital_cny * (1.0 - pref.cash_buffer_pct)
    target_positions = max(1, min(pref.max_positions, 10))
    per_name = min(investable / target_positions, pref.capital_cny * pref.max_single_position_pct)
    lines: list[OrderTicketLine] = []
    blockers: list[str] = []
    for c in screen.candidates:
        if len(lines) >= target_positions:
            break
        price = float(c.live_price or c.last_close or 0)
        if price <= 0:
            blockers.append(f"{c.symbol}: no valid price")
            continue
        if c.live_pct is not None and float(c.live_pct) >= 9.8:
            blockers.append(f"{c.symbol}: 接近涨停，不生成追高票据")
            continue
        qty = int(per_name / price) // 100 * 100
        if qty < 100:
            blockers.append(f"{c.symbol}: 用户资金/单票上限不足一手")
            continue
        lines.append(OrderTicketLine(
            symbol=c.symbol,
            side="BUY",
            quantity=qty,
            reference_price=round(price, 2),
            notional_cny=round(qty * price, 2),
            score=round(float(c.score), 3),
            sector=c.sector,
            rationale=c.reasons,
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

