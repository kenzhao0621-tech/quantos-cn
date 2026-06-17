"""Controlled live trading gates — execution levels, legal review, no auto real-money."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from gateway.config import ROOT

GATES_PATH = ROOT / "data" / "gateway" / "live_trading_gates.json"


class ExecutionLevel(int, Enum):
    READ_ONLY = 0
    SUGGEST_ONLY = 1
    DRAFT_CONFIRM = 2
    CONDITIONAL_AUTO = 3
    FULL_AUTO = 4


@dataclass
class LiveTradingGates:
    execution_level: int = ExecutionLevel.DRAFT_CONFIRM.value
    legal_review_required: bool = True
    legal_review_passed: bool = False
    max_daily_notional_cny: float = 5000.0
    max_single_order_cny: float = 2000.0
    user_confirmed_risk: bool = False
    real_money_enabled: bool = False
    unattended_auto_enabled: bool = False
    browser_auto_submit: bool = False
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_gates() -> LiveTradingGates:
    default_real = True
    try:
        from gateway import REAL_MONEY_EXECUTION_DISABLED

        default_real = not REAL_MONEY_EXECUTION_DISABLED
    except Exception:
        pass
    if not GATES_PATH.exists():
        return LiveTradingGates(real_money_enabled=default_real, user_confirmed_risk=default_real, legal_review_passed=default_real)
    raw = json.loads(GATES_PATH.read_text(encoding="utf-8"))
    return LiveTradingGates(
        execution_level=int(raw.get("execution_level", ExecutionLevel.DRAFT_CONFIRM.value)),
        legal_review_required=bool(raw.get("legal_review_required", True)),
        legal_review_passed=bool(raw.get("legal_review_passed", False)),
        max_daily_notional_cny=float(raw.get("max_daily_notional_cny", 5000)),
        max_single_order_cny=float(raw.get("max_single_order_cny", 2000)),
        user_confirmed_risk=bool(raw.get("user_confirmed_risk", False)),
        real_money_enabled=bool(raw.get("real_money_enabled", default_real)),
        unattended_auto_enabled=bool(raw.get("unattended_auto_enabled", False)),
        browser_auto_submit=bool(raw.get("browser_auto_submit", False)),
        updated_at=str(raw.get("updated_at") or ""),
    )


def save_gates(data: dict[str, Any]) -> LiveTradingGates:
    current = load_gates().to_dict()
    current.update({k: v for k, v in data.items() if k in current})
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    gates = LiveTradingGates(**current)  # type: ignore[arg-type]
    GATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    GATES_PATH.write_text(json.dumps(gates.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return gates


def can_submit_unattended_order(*, notional_cny: float, daily_used_cny: float = 0.0) -> dict[str, Any]:
    """Gates for unattended / conditional-auto execution (no per-order user click)."""
    gates = load_gates()
    blockers: list[str] = []
    if gates.legal_review_required and not gates.legal_review_passed:
        blockers.append("LEGAL_REVIEW_REQUIRED")
    if not gates.user_confirmed_risk:
        blockers.append("USER_RISK_NOT_CONFIRMED")
    if not gates.real_money_enabled:
        blockers.append("REAL_MONEY_DISABLED")
    if not gates.unattended_auto_enabled:
        blockers.append("UNATTENDED_NOT_ENABLED")
    if gates.execution_level < ExecutionLevel.CONDITIONAL_AUTO.value:
        blockers.append("EXECUTION_LEVEL_TOO_LOW")
    if gates.execution_level >= ExecutionLevel.FULL_AUTO.value:
        blockers.append("FULL_AUTO_REQUIRES_SIDECAR_ONLY")
    if notional_cny > gates.max_single_order_cny:
        blockers.append("SINGLE_ORDER_LIMIT")
    if daily_used_cny + notional_cny > gates.max_daily_notional_cny:
        blockers.append("DAILY_NOTIONAL_LIMIT")
    return {
        "allowed": len(blockers) == 0,
        "blockers": blockers,
        "execution_level": gates.execution_level,
        "gates": gates.to_dict(),
        "mode": "UNATTENDED_CONDITIONAL_AUTO",
    }


def can_submit_live_order(*, notional_cny: float, daily_used_cny: float = 0.0) -> dict[str, Any]:
    gates = load_gates()
    blockers: list[str] = []
    if gates.legal_review_required and not gates.legal_review_passed:
        blockers.append("LEGAL_REVIEW_REQUIRED")
    if not gates.user_confirmed_risk:
        blockers.append("USER_RISK_NOT_CONFIRMED")
    if not gates.real_money_enabled:
        blockers.append("REAL_MONEY_DISABLED")
    if gates.execution_level < ExecutionLevel.DRAFT_CONFIRM.value:
        blockers.append("EXECUTION_LEVEL_TOO_LOW")
    if gates.execution_level >= ExecutionLevel.FULL_AUTO.value:
        blockers.append("FULL_AUTO_NOT_ALLOWED_IN_THIS_BUILD")
    if notional_cny > gates.max_single_order_cny:
        blockers.append("SINGLE_ORDER_LIMIT")
    if daily_used_cny + notional_cny > gates.max_daily_notional_cny:
        blockers.append("DAILY_NOTIONAL_LIMIT")
    return {
        "allowed": len(blockers) == 0,
        "blockers": blockers,
        "execution_level": gates.execution_level,
        "gates": gates.to_dict(),
    }
