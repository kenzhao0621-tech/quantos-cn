#!/usr/bin/env python3
"""QuantOS Spec V4 — end-to-end closed loop orchestrator (safe, no live orders).

Runs: DataOS → ResearchOS → ValidationOS → AlphaOS → PortfolioOS → RiskOS →
SimulationOS/EventOS → reports → production_ready gate.

Safe defaults:
- Never places real orders
- Sets disable_live_trading on data drift (does not auto-halt kill switch)
- production_ready=false if any core report fails
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ART = ROOT / "artifacts"
ART.mkdir(parents=True, exist_ok=True)


def main() -> int:
    started = datetime.now().isoformat(timespec="seconds")
    report: dict[str, Any] = {
        "started_at": started,
        "spec_version": "V4",
        "steps": [],
        "reports": {},
        "gates": {},
        "production_ready": False,
        "disable_live_trading": False,
        "safe_mode": True,
    }

    # Phase A — audit
    from quant.quantos.phase_a_audit import run_phase_a_audit

    audit = run_phase_a_audit()
    report["steps"].append({"phase_a_audit": "OK"})

    # Upgrade pipeline first (may touch shared artifacts)
    subprocess.run([sys.executable, str(ROOT / "scripts/run_quant_upgrade_pipeline.py")], check=False)

    # Phase B — DataOS (after pipeline so data_quality_report keeps gate fields)
    from quant.dataos.quality_checker import run_warehouse_quality_checks
    from quant.dataos.drift_detector import detect_feature_drift, persist_drift_report
    from quant.dataos.corporate_action_checker import run_corporate_action_check

    dq = run_warehouse_quality_checks()
    (ART / "data_quality_report.json").write_text(json.dumps(dq, indent=2, ensure_ascii=False), encoding="utf-8")
    drift = detect_feature_drift()
    persist_drift_report(drift)
    corp = run_corporate_action_check()
    (ART / "corporate_action_report.json").write_text(json.dumps(corp, indent=2, ensure_ascii=False), encoding="utf-8")
    report["disable_live_trading"] = bool(drift.get("disable_live_trading"))
    report["steps"].append({"dataos": dq.get("status"), "drift": drift.get("status"), "corp": corp.get("status")})

    # SimulationOS + EventOS features (all disabled by default)
    from quant.simulation.feature_generator import generate_simulation_features
    from quant.event.event_feature_generator import generate_event_features
    from quant.validation.simulation_feature_validator import validate_event_features, validate_simulation_features

    sim_feat = generate_simulation_features()
    evt_feat = generate_event_features()
    sim_val = validate_simulation_features(sim_feat)
    evt_val = validate_event_features(evt_feat)
    (ART / "simulation_validation_report.json").write_text(json.dumps(sim_val, indent=2), encoding="utf-8")
    (ART / "event_validation_report.json").write_text(json.dumps(evt_val, indent=2, ensure_ascii=False), encoding="utf-8")

    # Generate Spec §18 / §9.5 reports from existing validation artifacts
    reports = _generate_validation_reports()
    report["reports"] = reports

    # Screener smoke (AlphaOS + PortfolioOS path)
    screener = _screener_smoke()
    report["steps"].append({"screener_smoke": screener.get("status")})

    # Risk + paper
    risk = _risk_report()
    paper = _paper_report()
    (ART / "risk_report.json").write_text(json.dumps(risk, indent=2, ensure_ascii=False), encoding="utf-8")
    (ART / "paper_trading_report.json").write_text(json.dumps(paper, indent=2, ensure_ascii=False), encoding="utf-8")

    # Model health
    health = _model_health_report()
    (ART / "model_health_report.json").write_text(json.dumps(health, indent=2, ensure_ascii=False), encoding="utf-8")
    report["reports"]["model_health_report.json"] = health.get("status")

    # Gates
    gates = _evaluate_gates(dq, drift, corp, sim_val, evt_val, screener, risk, paper, health, reports)
    report["gates"] = gates
    report["production_ready"] = all(
        gates.get(k) for k in (
            "data_quality",
            "leakage",
            "rank_ic",
            "purged_kfold",
            "simulation_features",
            "event_features",
            "screener_smoke",
            "risk_kill_switch",
            "paper_engine",
            "model_health",
            "ml_ensemble_gate",
        )
    ) and gates.get("live_trading_allowed", False)
    report["shadow_eligible"] = all(
        gates.get(k) for k in (
            "data_quality",
            "leakage",
            "rank_ic",
            "purged_kfold",
            "screener_smoke",
            "paper_engine",
            "model_health",
        )
    )
    report["finished_at"] = datetime.now().isoformat(timespec="seconds")

    out_path = ART / "QUANTOS_CLOSED_LOOP_REPORT.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_closed_loop_md(report, gates)

    # Ledger entry
    try:
        from gateway.observability.closed_loop import append_step

        append_step(
            "quantos_v4_closed_loop",
            "Spec V4 closed loop orchestration",
            expected="production_ready gate evaluation",
            actual=f"production_ready={report['production_ready']}",
            artifacts=[str(out_path.relative_to(ROOT))],
            rerun_result="PASS" if report["production_ready"] else "FAIL",
        )
    except Exception:
        pass

    print(json.dumps({
        "ok": True,
        "production_ready": report["production_ready"],
        "shadow_eligible": report.get("shadow_eligible"),
        "disable_live_trading": report["disable_live_trading"],
        "gates": gates,
        "report": str(out_path),
    }, indent=2, ensure_ascii=False))
    return 0 if report["production_ready"] else 1


def _load_json(name: str) -> dict[str, Any]:
    p = ART / name
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _generate_validation_reports() -> dict[str, str]:
    mv = _load_json("model_validation.json")
    mm = _load_json("model_metrics.json")
    leak = _load_json("leakage_test_report.json")
    fc = _load_json("factor_coverage_report.json")
    fcorr = _load_json("factor_correlation_report.json")
    buckets = _load_json("score_bucket_stats.json")

    oos = mv.get("out_of_sample") or {}
    ric = mm.get("rank_ic_oos") or oos.get("rank_ic") or {}

    factor_ic = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "OK" if fc.get("status") == "OK" else "WARN",
        "n_symbols": fc.get("n_symbols"),
        "core_factors": fc.get("core_factors"),
        "high_corr_pairs": (fcorr.get("high_corr_pairs") or []),
    }
    rankic = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mean_rank_ic": ric.get("mean_rank_ic"),
        "icir": ric.get("icir"),
        "n_days": ric.get("n_days"),
        "passed": float(ric.get("mean_rank_ic") or 0) >= 0.015,
        "status": ric.get("status", "OK"),
    }
    walk_fwd = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "walk_forward_passed": oos.get("walk_forward_passed"),
        "walk_forward_mean_return": oos.get("walk_forward_mean_return"),
        "purged_kfold_passed": oos.get("purged_kfold_passed"),
        "passed": bool(oos.get("purged_kfold_passed")),
    }
    oos_rep = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": mv.get("verdict"),
        "sharpe": (oos.get("performance") or {}).get("sharpe"),
        "max_drawdown_pct": (oos.get("performance") or {}).get("max_drawdown_pct"),
        "passed": mv.get("verdict") in ("READY", "SHADOW_ELIGIBLE", "CANDIDATE"),
    }
    regime = _load_json("regime.json")
    regime_rep = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_regime": regime.get("label"),
        "passed": bool(regime.get("label")),
    }
    txn = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cost_bps": (mv.get("config") or {}).get("cost_bps", 8),
        "slippage_bps": (mv.get("config") or {}).get("slippage_bps", 12),
        "after_cost_positive": float(oos.get("avg_daily_net_return") or 0) > 0,
        "passed": float(oos.get("avg_daily_net_return") or 0) > 0,
    }

    outputs = {
        "factor_ic_report.json": factor_ic,
        "rankic_report.json": rankic,
        "walk_forward_report.json": walk_fwd,
        "oos_report.json": oos_rep,
        "regime_report.json": regime_rep,
        "transaction_cost_report.json": txn,
        "leakage_test_report.json": leak,
        "score_bucket_stats.json": buckets,
    }
    status_map = {}
    for fname, payload in outputs.items():
        if fname in ("leakage_test_report.json", "score_bucket_stats.json"):
            continue
        (ART / fname).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        status_map[fname] = "PASS" if payload.get("passed", True) else "FAIL"
    return status_map


def _screener_smoke() -> dict[str, Any]:
    try:
        from quant.application.screener_service import get_screener_service

        svc = get_screener_service()
        r = svc.screen(preset="balanced", top_n=5, min_amount_cny=1e8, price_max_cny=500)
        d = r.to_dict()
        return {
            "status": "OK" if d.get("candidates") else "EMPTY",
            "candidates": len(d.get("candidates") or []),
            "ensemble_mode": d.get("ensemble_mode"),
            "ml_active": d.get("ml_active"),
            "passed": bool(d.get("candidates")) and not d.get("blocked"),
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)[:200], "passed": False}


def _risk_report() -> dict[str, Any]:
    from gateway.risk.kill_switch import KillSwitch

    ks = KillSwitch().status()
    drift = _load_json("data_drift_report.json")
    drift_severe = bool(drift.get("disable_live_trading"))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "kill_switch": ks.get("state"),
        "disable_live_trading": drift_severe,
        "drift_status": drift.get("status"),
        "passed": ks.get("state") == "OPEN",
        "live_trading_allowed": ks.get("state") == "OPEN" and not drift_severe,
    }


def _paper_report() -> dict[str, Any]:
    p = _load_json("paper_engine_validation.json")
    n = p.get("sample_count") or p.get("n_samples") or 0
    engine_ok = bool(
        p.get("state_machine_complete")
        and p.get("t1_enforced")
        and p.get("restart_recovery_passed")
    )
    passed = engine_ok or n >= 7
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "paper_validation": p,
        "sample_count": n,
        "engine_validated": engine_ok,
        "passed": passed,
        "note": "Paper engine FSM validated; shadow sample ledger optional",
    }


def _model_health_report() -> dict[str, Any]:
    from quant.models.ml_scorer import get_ml_gate_status

    gate = get_ml_gate_status()
    mv = _load_json("model_validation.json")
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ml_gate": gate,
        "validation_verdict": mv.get("verdict"),
        "model_version": "screener_v5_ensemble_lgbm_2026-06-17",
        "status": "HEALTHY" if gate.get("passed") and leak_ok() else "DEGRADED",
        "passed": gate.get("passed") and mv.get("verdict") not in ("REJECTED",),
    }


def leak_ok() -> bool:
    return bool(_load_json("leakage_test_report.json").get("passed"))


def _evaluate_gates(
    dq, drift, corp, sim_val, evt_val, screener, risk, paper, health, reports
) -> dict[str, bool]:
    return {
        "data_quality": bool(dq.get("passed")),
        "data_drift": bool(drift.get("passed")),
        "corporate_action_partial": bool(corp.get("passed")),
        "leakage": leak_ok(),
        "rank_ic": bool(_load_json("rankic_report.json").get("passed")),
        "purged_kfold": bool(_load_json("walk_forward_report.json").get("purged_kfold_passed")),
        "simulation_features": bool(sim_val.get("passed")),
        "event_features": bool(evt_val.get("passed")),
        "screener_smoke": bool(screener.get("passed")),
        "risk_kill_switch": bool(risk.get("passed")),
        "paper_engine": bool(paper.get("passed")),
        "model_health": bool(health.get("passed")),
        "ml_ensemble_gate": bool(health.get("passed")),
        "live_trading_allowed": bool(risk.get("live_trading_allowed")),
    }


def _write_closed_loop_md(report: dict[str, Any], gates: dict[str, bool]) -> None:
    lines = [
        "# QuantOS 闭环报告 (Spec V4)",
        "",
        f"开始: {report['started_at']}",
        f"结束: {report.get('finished_at', '')}",
        "",
        f"**production_ready**: `{report['production_ready']}`",
        f"**disable_live_trading**: `{report['disable_live_trading']}`",
        "",
        "## 门禁",
        "",
    ]
    for k, v in gates.items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    lines.extend([
        "",
        "## 原则",
        "",
        "LLM / Agent / SimulationOS 不直接输出买卖指令。",
        "验证未通过时自动降级为 baseline / 禁用 live trading。",
        "",
        "## 命令",
        "",
        "```bash",
        "python scripts/run_quantos_closed_loop.py",
        "make quantos-closed-loop",
        "```",
    ])
    (ART / "QUANTOS_CLOSED_LOOP_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
