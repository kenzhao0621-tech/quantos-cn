"""Deployment eligibility — backend-calculated lifecycle stages."""

from __future__ import annotations

from enum import Enum
from typing import Any

from gateway.config import ROOT


class DeploymentStage(str, Enum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    SHADOW_ELIGIBLE = "SHADOW_ELIGIBLE"
    PAPER_ELIGIBLE = "PAPER_ELIGIBLE"
    SIMULATED_BROKER_ELIGIBLE = "SIMULATED_BROKER_ELIGIBLE"
    MANUAL_LIVE_ELIGIBLE = "MANUAL_LIVE_ELIGIBLE"
    BLOCKED = "BLOCKED"


def compute_deployment_eligibility(*, e2e_passed: bool | None = None) -> dict[str, Any]:
    """Evaluate gates from validation, paper, broker, and engineering artifacts."""
    blockers: list[str] = []
    gates: dict[str, bool] = {}

    # Metric audit
    metric_path = ROOT / "artifacts" / "metric_registry.json"
    gates["metric_audit_completed"] = metric_path.exists()
    if not gates["metric_audit_completed"]:
        blockers.append("METRIC_REGISTRY_MISSING")

    # Validation
    val_path = ROOT / "artifacts" / "strict_validation.json"
    validation: dict[str, Any] = {}
    if val_path.exists():
        import json
        validation = json.loads(val_path.read_text(encoding="utf-8"))
    gates["dsr_verified"] = validation.get("dsr_verified", False)
    gates["pbo_verified"] = validation.get("pbo_status") in ("OK", "INSUFFICIENT_SAMPLE")
    gates["true_rank_ic"] = validation.get("true_rank_ic_implemented", False)
    gates["net_oos_positive"] = validation.get("net_oos_cumulative_return_pct", 0) > 0

    # Paper engine
    paper_path = ROOT / "artifacts" / "paper_engine_validation.json"
    paper: dict[str, Any] = {}
    if paper_path.exists():
        import json
        paper = json.loads(paper_path.read_text(encoding="utf-8"))
    gates["paper_state_machine"] = paper.get("state_machine_complete", False)
    gates["t1_enforced"] = paper.get("t1_enforced", False)

    # E2E
    e2e_path = ROOT / "artifacts" / "e2e_results.json"
    if e2e_passed is None and e2e_path.exists():
        import json
        e2e = json.loads(e2e_path.read_text(encoding="utf-8"))
        e2e_passed = e2e.get("all_passed", False)
    gates["critical_e2e"] = bool(e2e_passed)
    if not gates["critical_e2e"]:
        blockers.append("CRITICAL_E2E_FAILED")

    # Broker dry-run
    broker_path = ROOT / "artifacts" / "shadow_paper_broker_validation.json"
    broker_ok = False
    if broker_path.exists():
        import json
        broker_ok = json.loads(broker_path.read_text(encoding="utf-8")).get("broker_dry_run_passed", False)
    gates["broker_dry_run"] = broker_ok

    # Determine stage
    stage = DeploymentStage.RESEARCH_ONLY
    if gates["metric_audit_completed"] and gates["true_rank_ic"] and gates["critical_e2e"]:
        stage = DeploymentStage.SHADOW_ELIGIBLE
    if stage == DeploymentStage.SHADOW_ELIGIBLE and gates["paper_state_machine"] and gates["t1_enforced"]:
        if gates.get("net_oos_positive") and validation.get("sample_status") in ("PRELIMINARY", "MODERATE", "MATURE"):
            stage = DeploymentStage.PAPER_ELIGIBLE
        elif not gates.get("net_oos_positive"):
            blockers.append("NET_OOS_RETURN_NEGATIVE")
    if stage == DeploymentStage.PAPER_ELIGIBLE and gates["broker_dry_run"]:
        stage = DeploymentStage.SIMULATED_BROKER_ELIGIBLE
    if stage == DeploymentStage.SIMULATED_BROKER_ELIGIBLE:
        if not (gates["dsr_verified"] and gates["net_oos_positive"] and validation.get("pbo_passed")):
            blockers.append("MANUAL_LIVE_GATES_NOT_MET")
        else:
            stage = DeploymentStage.MANUAL_LIVE_ELIGIBLE

    from gateway.live_trading.gates import load_gates

    g = load_gates()
    unattended_ok = (
        g.unattended_auto_enabled
        and g.execution_level >= 3
        and g.real_money_enabled
        and stage in (DeploymentStage.MANUAL_LIVE_ELIGIBLE, DeploymentStage.SIMULATED_BROKER_ELIGIBLE, DeploymentStage.PAPER_ELIGIBLE)
    )

    if blockers and stage == DeploymentStage.RESEARCH_ONLY:
        stage = DeploymentStage.BLOCKED if "CRITICAL_E2E_FAILED" in blockers else stage

    return {
        "deployment_eligibility": stage.value,
        "gates": gates,
        "blockers": blockers,
        "unattended_live_prohibited": not unattended_ok,
        "unattended_live_available": unattended_ok,
        "manual_confirmation_required": not g.unattended_auto_enabled,
    }
