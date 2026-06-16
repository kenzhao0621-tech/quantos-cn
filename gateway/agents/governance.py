"""Tool/MCP governance hooks."""

from __future__ import annotations

from typing import Any

BLOCKED_TOOLS_FOR_EXECUTION = {"live_order_submit", "broker_live_connect", "gc_mgc_live_route"}


def validate_tool_invocation(
    tool_name: str,
    *,
    agent_type: str,
    mode: str,
    sidecar: bool = False,
) -> tuple[bool, str]:
    if tool_name in BLOCKED_TOOLS_FOR_EXECUTION:
        return False, "tool_blocked_in_this_batch"
    if sidecar and tool_name.startswith("ashare_execute"):
        return False, "sidecar_cannot_invoke_ashare_execution"
    if agent_type == "sidecar_research" and "execute" in tool_name:
        return False, "sidecar_research_no_execution_tools"
    if mode == "HALTED":
        return False, "system_halted"
    return True, "ok"


def governance_report(catalog_agents: list[dict[str, Any]]) -> dict[str, Any]:
    sidecar = [a for a in catalog_agents if a.get("isolated")]
    return {
        "blocked_tools": sorted(BLOCKED_TOOLS_FOR_EXECUTION),
        "sidecar_agents": [a["id"] for a in sidecar],
        "execution_bypass_allowed": False,
    }
