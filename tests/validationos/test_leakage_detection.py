"""Reliability upgrade tests."""

from quant.validation.leakage_detector import run_leakage_audit


def test_leakage_audit_runs():
    report = run_leakage_audit()
    assert "checks" in report
    assert "passed" in report


def test_disclosure_pit_in_screener():
    from quant.application.screener_service import _load_disclosure_map

    old = _load_disclosure_map("2020-01-01")
    new = _load_disclosure_map("2099-12-31")
    assert len(new) >= len(old)
