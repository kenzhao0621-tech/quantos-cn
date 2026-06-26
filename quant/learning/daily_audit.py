"""LearningOS — daily audit: drift, decay, validation failure."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts"


def run_daily_audit() -> dict[str, Any]:
    from quant.dataos.drift_detector import detect_feature_drift
    from quant.learning.factor_decay import detect_factor_decay
    from quant.models.ml_scorer import get_ml_gate_status
    from quant.validation.leakage_detector import run_leakage_audit

    drift = detect_feature_drift()
    decay = detect_factor_decay()
    leak = run_leakage_audit()
    ml = get_ml_gate_status()
    actions: list[str] = []
    if not drift.get("passed"):
        actions.append("disable_live_trading")
    if not ml.get("passed"):
        actions.append("fallback_to_baseline_ensemble")
    if not leak.get("passed"):
        actions.append("production_ready=false")
    for f in decay.get("decayed_factors") or []:
        actions.append(f"disable_or_downweight:{f}")

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_drift": drift,
        "factor_decay": decay,
        "leakage": {"passed": leak.get("passed")},
        "ml_gate": ml,
        "actions": actions,
        "model_health": "HEALTHY" if ml.get("passed") and drift.get("passed") else "DEGRADED",
    }
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "daily_audit_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = [
        "# Daily Audit Report",
        "",
        f"Time: {report['generated_at']}",
        f"Model health: **{report['model_health']}**",
        "",
        "## Actions",
    ]
    md.extend(f"- {a}" for a in actions)
    (ART / "daily_audit_report.md").write_text("\n".join(md), encoding="utf-8")
    (ART / "model_health.json").write_text(json.dumps({
        "generated_at": report["generated_at"],
        "status": report["model_health"],
        "ml_gate": ml,
        "drift_passed": drift.get("passed"),
    }, indent=2), encoding="utf-8")
    return report


def run_data_check() -> dict[str, Any]:
    from quant.dataos.quality_checker import run_warehouse_quality_checks

    return run_warehouse_quality_checks()
