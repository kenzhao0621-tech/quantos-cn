"""AgentsOS — TradingAgents-CN style structured multi-agent research pipeline.

All agents consume ONE strict JSON input (build_agent_input) and emit the §7.3
JSON contract. The default engine is deterministic rules over real structured
data — agents never free-read the network or invent numbers. RiskManager holds
veto power; FinalAdvisor emits A/B/C/D/BLOCKED with evidence and失效条件.
"""

from gateway.agents.quantos.pipeline import run_agents_analysis

__all__ = ["run_agents_analysis"]
