"""Execution preflight tests."""

from gateway.execution.preflight import execution_preflight


def test_preflight_paper_mode_structure():
    pre = execution_preflight(mode="paper")
    assert "allowed" in pre
    assert "blockers" in pre
    assert "closed_loop" in pre
