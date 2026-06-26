"""Phase A audit — architecture, factor, risk, validation snapshots."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts"


def run_phase_a_audit() -> dict[str, Any]:
    ART.mkdir(parents=True, exist_ok=True)
    arch = _architecture_audit()
    factor = _factor_audit()
    risk = _risk_audit()
    validation = _validation_audit()

    (ART / "current_architecture_audit.md").write_text(_arch_md(arch), encoding="utf-8")
    (ART / "current_factor_audit.json").write_text(json.dumps(factor, indent=2, ensure_ascii=False), encoding="utf-8")
    (ART / "current_risk_audit.json").write_text(json.dumps(risk, indent=2, ensure_ascii=False), encoding="utf-8")
    (ART / "current_validation_audit.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "architecture": arch,
        "factor": factor,
        "risk": risk,
        "validation": validation,
    }


def _architecture_audit() -> dict[str, Any]:
    modules = {
        "DataOS": ["quant/dataos/quality_checker.py", "quant/dataos/drift_detector.py"],
        "ResearchOS": ["quant/features/factor_library.py", "configs/factor_registry.yaml"],
        "SimulationOS": ["quant/simulation/state_engine.py", "quant/simulation/feature_generator.py"],
        "EventOS": ["quant/event/event_classifier.py", "quant/event/event_graph.py"],
        "ValidationOS": ["quant/validation/purged_kfold.py", "quant/validation/walk_forward.py"],
        "AlphaOS": ["quant/models/lgbm_ranker.py", "quant/models/ensemble.py", "quant/models/ml_scorer.py"],
        "PortfolioOS": ["quant/portfolio/optimizer.py", "quant/portfolio/cost_model.py"],
        "RiskOS": ["gateway/risk/engine.py", "gateway/risk/kill_switch.py"],
        "ExecutionOS": ["gateway/paper/engine.py", "quant/tradability/mask.py"],
        "ExplainabilityOS": ["quant/explain/bucket_stats.py", "quant/scoring/enrichment.py"],
        "LearningOS": ["quant/learning/outcome_tracker.py", "quant/dataos/drift_detector.py"],
        "UserOS": ["apps/portal-web/index.html", "apps/portal-web/app.js"],
    }
    present = {}
    for os_name, files in modules.items():
        present[os_name] = {f: (ROOT / f).exists() for f in files}
    return {
        "product": "QuantOS CN",
        "spec_version": "V4",
        "modules": present,
        "orchestrators": [
            "scripts/run_quant_upgrade_pipeline.py",
            "scripts/run_quantos_closed_loop.py",
            "scripts/run-daily-quant-pipeline.py",
        ],
        "principle": "LLM/Agent/SimulationOS never emit direct trade orders",
    }


def _arch_md(arch: dict[str, Any]) -> str:
    lines = [
        "# QuantOS 当前架构审计 (Spec V4 Phase A)",
        "",
        f"生成时间: {arch.get('generated_at', datetime.now().isoformat(timespec='seconds'))}",
        "",
        "## OS 模块覆盖",
        "",
    ]
    for os_name, files in arch["modules"].items():
        ok = sum(1 for v in files.values() if v)
        total = len(files)
        lines.append(f"- **{os_name}**: {ok}/{total} 核心文件就绪")
    lines.extend([
        "",
        "## 原则",
        "",
        arch["principle"],
        "",
        "## 编排器",
        "",
    ])
    for o in arch["orchestrators"]:
        lines.append(f"- `{o}`")
    return "\n".join(lines)


def _factor_audit() -> dict[str, Any]:
    reg_path = ROOT / "configs" / "factor_registry.yaml"
    return {
        "registry_yaml": reg_path.exists(),
        "registry_json": (ART / "factor_registry.json").exists(),
        "alpha158_cache": (ROOT / "data/parquet/features/alpha158/alpha158_wide.parquet").exists(),
        "neutralization": "quant/features/neutralization.py",
        "model_version": "screener_v5_ensemble_lgbm_2026-06-17",
        "ensemble_weights": {"ml": 0.45, "baseline": 0.35, "risk": 0.20},
    }


def _risk_audit() -> dict[str, Any]:
    from gateway.risk.kill_switch import KillSwitch

    ks = KillSwitch().status()
    return {
        "kill_switch_state": ks.get("state"),
        "constraints": {
            "single_stock_weight_max": 0.05,
            "single_industry_weight_max": 0.15,
            "ST_forbidden": True,
            "limit_up_buy_forbidden": True,
        },
        "paper_engine": (ART / "paper_engine_validation.json").exists(),
    }


def _validation_audit() -> dict[str, Any]:
    paths = [
        "model_validation.json",
        "model_metrics.json",
        "leakage_test_report.json",
        "score_bucket_stats.json",
    ]
    loaded = {}
    for p in paths:
        fp = ART / p
        loaded[p] = fp.exists()
        if fp.exists():
            try:
                loaded[p + ":verdict"] = json.loads(fp.read_text(encoding="utf-8")).get("verdict") or json.loads(
                    fp.read_text(encoding="utf-8")
                ).get("passed")
            except Exception:
                pass
    return {"artifacts_present": loaded, "validation_os_modules": ["purged_kfold", "walk_forward", "leakage_detector"]}
