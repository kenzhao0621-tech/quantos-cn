"""Agent catalog and model routing governance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from gateway.config import load_agents_catalog


@dataclass
class AgentSpec:
    id: str
    name: str
    type: str
    allowed_modes: list[str]
    tools: list[str]
    max_tokens_per_run: int
    isolated: bool = False
    execution_bypass_allowed: bool = False


class AgentCatalog:
    def __init__(self, catalog: dict[str, Any] | None = None) -> None:
        self.raw = catalog or load_agents_catalog()
        self.agents = {
            a["id"]: AgentSpec(
                id=a["id"],
                name=a["name"],
                type=a["type"],
                allowed_modes=list(a.get("allowed_modes", [])),
                tools=list(a.get("tools", [])),
                max_tokens_per_run=int(a.get("max_tokens_per_run", 8000)),
                isolated=bool(a.get("isolated", False)),
                execution_bypass_allowed=bool(a.get("execution_bypass_allowed", False)),
            )
            for a in self.raw.get("agents", [])
        }
        self.model_routes = self.raw.get("model_routes", [])

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "allowed_modes": a.allowed_modes,
                "tools": a.tools,
                "isolated": a.isolated,
            }
            for a in self.agents.values()
        ]

    def get(self, agent_id: str) -> Optional[AgentSpec]:
        return self.agents.get(agent_id)

    def route_model(self, agent_id: str) -> dict[str, Any]:
        agent = self.get(agent_id)
        if not agent:
            return {"error": "agent_not_found"}
        allowed_types = set()
        for route in self.model_routes:
            allowed_types.update(route.get("allowed_agent_types", []))
        for route in self.model_routes:
            if agent.type in route.get("allowed_agent_types", []):
                return {"route_id": route["id"], "provider": route["provider"], "model": route["model"]}
        return {"route_id": "local-deterministic", "provider": "local", "model": "deterministic-fixture"}

    def can_invoke(self, agent_id: str, mode: str) -> tuple[bool, str]:
        agent = self.get(agent_id)
        if not agent:
            return False, "agent_not_found"
        if mode not in agent.allowed_modes and mode != "HALTED":
            return False, f"agent_not_allowed_in_mode_{mode}"
        if agent.isolated and agent.type == "sidecar_research":
            return True, "sidecar_research_only"
        return True, "ok"
