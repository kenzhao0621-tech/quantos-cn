"""Unified platform health — data, jobs, learning, promotion readiness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.config import ROOT
from gateway.data_gate import evaluate_data_gate


def _jobs_summary() -> dict[str, Any]:
    path = ROOT / "data" / "gateway" / "jobs.json"
    if not path.exists():
        return {"total": 0, "failed_recent": 0}
    try:
        jobs = json.loads(path.read_text(encoding="utf-8"))
        items = list(jobs.values()) if isinstance(jobs, dict) else jobs
        failed = sum(1 for j in items[-20:] if j.get("status") == "FAILED")
        running = sum(1 for j in items if j.get("status") == "RUNNING")
        return {"total": len(items), "failed_recent": failed, "running": running}
    except Exception:
        return {"total": 0, "failed_recent": 0}


def _promotion_readiness() -> dict[str, Any]:
    from quant.application.model_validation_service import ValidationConfig, get_model_validation_service
    from quant.learning.outcome_tracker import compute_learning_summary

    validation = get_model_validation_service().validate(ValidationConfig(lookback_days=30, top_n=8)).to_dict()
    learning = compute_learning_summary()
    paper_path = ROOT / "data" / "gateway" / "paper_signals.jsonl"
    shadow_path = ROOT / "data" / "gateway" / "shadow_orders.jsonl"
    paper_n = sum(1 for _ in paper_path.open(encoding="utf-8")) if paper_path.exists() else 0
    shadow_n = sum(1 for _ in shadow_path.open(encoding="utf-8")) if shadow_path.exists() else 0

    gates = {
        "data_ok": validation.get("verdict") != "BLOCKED_BY_DATA",
        "validation_pass": validation.get("verdict") == "READY_FOR_EXTENDED_PAPER",
        "learning_samples": learning.get("scored_days", 0) >= 5,
        "paper_track": paper_n >= 3,
        "shadow_track": shadow_n >= 1,
    }
    stage = "research"
    if gates["data_ok"] and gates["learning_samples"]:
        stage = "validated_research"
    if gates["validation_pass"] and gates["paper_track"]:
        stage = "paper_soak"
    if gates["validation_pass"] and gates["paper_track"] and gates["shadow_track"]:
        stage = "assisted_live_ready"

    return {
        "stage": stage,
        "gates": gates,
        "validation_verdict": validation.get("verdict"),
        "learning_status": learning.get("status"),
        "paper_signals": paper_n,
        "shadow_events": shadow_n,
        "next_actions": validation.get("actions", [])[:3] + learning.get("recommendations", [])[:2],
    }


def get_platform_health(*, probe_live: bool = False) -> dict[str, Any]:
    data_gate = evaluate_data_gate(probe_live=probe_live)
    learning = __import__("quant.learning.outcome_tracker", fromlist=["compute_learning_summary"]).compute_learning_summary()
    return {
        "data_gate": data_gate,
        "jobs": _jobs_summary(),
        "learning": learning,
        "promotion": _promotion_readiness(),
        "real_execution": {
            "auto_real_orders": False,
            "mode": "MANUAL_CONFIRM_ONLY",
            "supported": ["paper", "shadow", "order_ticket", "broker_handoff", "fill_reconciliation"],
        },
    }
