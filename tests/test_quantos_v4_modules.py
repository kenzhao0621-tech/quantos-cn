"""QuantOS Spec V4 module smoke tests."""

from __future__ import annotations


def test_simulation_forbidden_outputs():
    from quant.simulation.state_engine import build_market_state

    state = build_market_state()
    assert "BUY" in state["forbidden_outputs"]
    assert state["regime"] in ("bull", "bear", "sideways", "high_volatility", "sideway")


def test_simulation_features_disabled_by_default():
    from quant.simulation.feature_generator import generate_simulation_features

    out = generate_simulation_features()
    assert out["production_enabled_count"] == 0
    assert "BUY" in out["forbidden"]


def test_event_classifier():
    from quant.event.event_classifier import classify_disclosure

    ev = classify_disclosure({"severity": "HIGH", "title": "审计问题"})
    assert ev["category"] == "audit_issue"


def test_dataos_quality_structure():
    from quant.dataos.quality_checker import run_warehouse_quality_checks

    dq = run_warehouse_quality_checks()
    assert "checks" in dq
    assert "passed" in dq


def test_phase_a_audit_writes_artifacts(tmp_path, monkeypatch):
    from quant import quantos

    art = tmp_path / "artifacts"
    monkeypatch.setattr(quantos.phase_a_audit, "ART", art)
    result = quantos.phase_a_audit.run_phase_a_audit()
    assert (art / "current_architecture_audit.md").exists()
    assert (art / "current_factor_audit.json").exists()
    assert result["architecture"]["product"] == "QuantOS CN"


def test_simulation_validator_blocks_unvalidated_enabled():
    from quant.validation.simulation_feature_validator import validate_simulation_features

    bad = validate_simulation_features({
        "candidate_features": {
            "x": {"enabled": True, "validation_status": "NOT_RUN"},
        }
    })
    assert bad["passed"] is False
