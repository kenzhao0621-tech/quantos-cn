"""QuantOS unified service entry — Spec §13."""

from __future__ import annotations

from typing import Any


def run_data_check() -> dict[str, Any]:
    from quant.learning.daily_audit import run_data_check

    return run_data_check()


def run_factor_pipeline(*, as_of_date: str | None = None) -> dict[str, Any]:
    from quant.application.screener_service import get_screener_service

    svc = get_screener_service()
    as_of, scored, _, blocker = svc._score_universe(as_of_date=as_of_date, min_amount_cny=5e7)
    return {"as_of_date": as_of, "n_scored": len(scored), "blocker": blocker}


def run_validation() -> dict[str, Any]:
    from quant.validation.leakage_detector import persist_leakage_report

    path = persist_leakage_report()
    from quant.application.model_validation_service import ModelValidationService

    result = ModelValidationService().validate()
    return {"leakage_report": str(path), "verdict": result.verdict}


def run_portfolio_construction(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    from quant.portfolio.optimizer import optimize_topk

    return optimize_topk(candidates)


def run_risk_check() -> dict[str, Any]:
    from gateway.risk.kill_switch import KillSwitch
    from quant.risk.exposure_report import compute_exposure_report

    ks = KillSwitch().status()
    return {"kill_switch": ks, "exposure": compute_exposure_report()}


def run_paper_trading_status() -> dict[str, Any]:
    from pathlib import Path
    import json

    p = Path(__file__).resolve().parents[2] / "artifacts" / "paper_trading_report.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"status": "NOT_RUN"}


def generate_daily_report() -> dict[str, Any]:
    from quant.learning.daily_audit import run_daily_audit

    return run_daily_audit()
