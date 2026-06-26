"""ValidationOS — simulation/event feature gate (Spec §9.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def validate_simulation_features(features: dict[str, Any]) -> dict[str, Any]:
    candidates = features.get("candidate_features") or {}
    rows = []
    for name, meta in candidates.items():
        enabled = bool(meta.get("enabled"))
        status = meta.get("validation_status", "NOT_RUN")
        passed = enabled and status == "APPROVED"
        rows.append({
            "feature": name,
            "enabled": enabled,
            "validation_status": status,
            "passed": passed,
            "required_oos_rank_ic": 0.015,
            "actual_oos_rank_ic": None,
        })
    any_enabled_unvalidated = any(r["enabled"] and not r["passed"] for r in rows)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "passed": not any_enabled_unvalidated,
        "features": rows,
        "production_enabled_count": sum(1 for r in rows if r["enabled"]),
    }


def validate_event_features(features: dict[str, Any]) -> dict[str, Any]:
    candidates = features.get("candidate_features") or {}
    rows = []
    for name, meta in candidates.items():
        status = meta.get("validation_status", "NOT_RUN")
        enabled = bool(meta.get("enabled"))
        passed = not enabled or status in ("APPROVED", "PARTIAL")
        rows.append({"feature": name, "enabled": enabled, "validation_status": status, "passed": passed})
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "passed": all(r["passed"] for r in rows),
        "features": rows,
    }
