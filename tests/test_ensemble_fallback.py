"""Ensemble gate + LGBM fallback behaviour."""

from __future__ import annotations

from unittest.mock import patch

from quant.models.ensemble import ensemble_score, validation_gate
from quant.models.ml_scorer import apply_ensemble_to_rows, get_ml_gate_status, invalidate_gate_cache


def test_ensemble_weights_when_ml_passed():
    baseline = {"A": 1.0, "B": 2.0, "C": 0.5}
    ml = {"A": 3.0, "B": 1.0, "C": 2.0}
    risk = {"A": 0.0, "B": 1.0, "C": 2.0}
    out = ensemble_score(baseline, ml, risk, ml_passed=True)
    assert set(out) == {"A", "B", "C"}
    assert all(0 <= v <= 1 for v in out.values())


def test_ensemble_degrades_to_baseline_only():
    baseline = {"A": 1.0, "B": 3.0}
    ml = {"A": 10.0, "B": 0.1}
    out_fail = ensemble_score(baseline, ml, None, ml_passed=False)
    out_none = ensemble_score(baseline, None, None, ml_passed=True)
    # Baseline-only path: rank-normalized baseline (B ranks above A).
    assert out_fail["B"] > out_fail["A"]
    assert out_none == out_fail


def test_validation_gate_reads_rank_ic_oos():
    metrics = {
        "train": {"trained": True},
        "rank_ic_oos": {"mean_rank_ic": 0.05, "icir": 0.5},
        "cost_adjusted_return_positive": True,
    }
    assert validation_gate(metrics) is True
    metrics["rank_ic_oos"]["mean_rank_ic"] = 0.01
    assert validation_gate(metrics) is False


def test_apply_ensemble_rows_fallback(monkeypatch):
    invalidate_gate_cache()
    monkeypatch.setattr(
        "quant.models.ml_scorer.get_ml_gate_status",
        lambda: {"passed": False, "mode": "baseline_fallback", "reasons": ["test"], "weights": {}},
    )
    raw = [
        {"symbol": "600519.SH", "baseline_score": 2.0, "score": 2.0},
        {"symbol": "000001.SZ", "baseline_score": 1.0, "score": 1.0},
    ]
    z = {"vol_20": {"600519.SH": 0.5, "000001.SZ": 1.0}}
    gate = apply_ensemble_to_rows(raw, as_of_date="2026-06-16", z=z, mode="eod")
    assert gate["mode"] == "baseline_fallback"
    assert raw[0]["ensemble_mode"] == "baseline_fallback"
    assert raw[0].get("ml_score") is None


def test_gate_passes_with_current_artifacts():
    invalidate_gate_cache()
    status = get_ml_gate_status()
    assert status["passed"] is True
    assert status["mode"] == "ensemble_lgbm"
