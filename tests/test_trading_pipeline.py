"""Trading pipeline integration tests."""

from gateway.trading_pipeline import execute_allocation_lines


def test_execute_allocation_blocked_without_positions():
    r = execute_allocation_lines({"positions": []}, user_id="test", unattended=False)
    assert r["ok"] is False
    assert "NO_EXECUTABLE_POSITIONS" in (r.get("blockers") or [""])[0] or any(
        "NO_EXECUTABLE" in b for b in (r.get("blockers") or [])
    )
