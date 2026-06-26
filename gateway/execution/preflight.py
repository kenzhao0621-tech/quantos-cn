"""Execution preflight — unified gates before paper/live orders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _closed_loop() -> dict[str, Any]:
    p = ROOT / "artifacts" / "QUANTOS_CLOSED_LOOP_REPORT.json"
    if not p.exists():
        return {"shadow_eligible": False, "production_ready": False, "disable_live_trading": True}
    return json.loads(p.read_text(encoding="utf-8"))


def execution_preflight(
    *,
    mode: str = "paper",
    unattended: bool = False,
    allow_drift_override: bool = False,
) -> dict[str, Any]:
    """Check kill switch, platform readiness, live gates."""
    from gateway.live_trading.gates import can_submit_live_order, can_submit_unattended_order, load_gates
    from gateway.risk.kill_switch import KillSwitch

    blockers: list[str] = []
    warnings: list[str] = []
    loop = _closed_loop()
    gates = load_gates()

    if KillSwitch().is_halted:
        blockers.append("KILL_SWITCH_HALTED")

    if not loop.get("shadow_eligible", False):
        blockers.append("PLATFORM_SHADOW_NOT_ELIGIBLE")

    if loop.get("disable_live_trading"):
        if allow_drift_override or unattended:
            warnings.append("DATA_DRIFT_DETECTED")
        else:
            blockers.append("DATA_DRIFT_DISABLE_LIVE")

    if mode == "paper":
        pass  # shadow_eligible sufficient
    elif mode in ("live", "real"):
        if not gates.real_money_enabled:
            blockers.append("REAL_MONEY_DISABLED")
        if not gates.user_confirmed_risk:
            blockers.append("USER_RISK_NOT_CONFIRMED")
        if gates.legal_review_required and not gates.legal_review_passed:
            blockers.append("LEGAL_REVIEW_REQUIRED")
    elif mode == "unattended" or unattended:
        gate = can_submit_unattended_order(notional_cny=0)
        if not gate.get("allowed"):
            blockers.extend(gate.get("blockers") or [])
        if not gates.unattended_auto_enabled:
            blockers.append("UNATTENDED_NOT_ENABLED")

    return {
        "allowed": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "mode": mode,
        "unattended": unattended,
        "closed_loop": {
            "shadow_eligible": loop.get("shadow_eligible"),
            "production_ready": loop.get("production_ready"),
            "disable_live_trading": loop.get("disable_live_trading"),
        },
        "gates": gates.to_dict(),
    }
