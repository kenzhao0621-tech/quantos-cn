"""Simulation Feature Generator — all features disabled until ValidationOS passes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quant.simulation.causal_graph import load_causal_graph
from quant.simulation.state_engine import build_market_state
from quant.simulation.theme_rotation import compute_theme_strength

SIMULATION_FEATURES: dict[str, dict[str, Any]] = {
    "policy_support_score": {"enabled": False, "validation_status": "NOT_RUN"},
    "policy_restriction_score": {"enabled": False, "validation_status": "NOT_RUN"},
    "theme_strength_score": {"enabled": False, "validation_status": "NOT_RUN"},
    "theme_persistence_score": {"enabled": False, "validation_status": "NOT_RUN"},
    "causal_strength_score": {"enabled": False, "validation_status": "NOT_RUN"},
    "scenario_consensus_score": {"enabled": False, "validation_status": "NOT_RUN"},
    "event_persistence_score": {"enabled": False, "validation_status": "NOT_RUN"},
    "counterfactual_alpha_score": {"enabled": False, "validation_status": "NOT_RUN"},
}


def generate_simulation_features(*, as_of_date: str | None = None) -> dict[str, Any]:
    state = build_market_state(as_of_date=as_of_date)
    themes = compute_theme_strength()
    graph = load_causal_graph()
    avg_theme = 0.5
    if themes.get("theme_strength"):
        avg_theme = sum(t["strength"] for t in themes["theme_strength"]) / len(themes["theme_strength"])

    candidates = {
        name: {
            **meta,
            "value": round(avg_theme if "theme" in name else 0.5, 4),
            "source": "simulation_os",
        }
        for name, meta in SIMULATION_FEATURES.items()
    }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "market_state": state,
        "causal_graph_edge_count": len(graph.get("edges", [])),
        "theme_count": len(themes.get("theme_strength", [])),
        "candidate_features": candidates,
        "production_enabled_count": sum(1 for c in candidates.values() if c.get("enabled")),
        "forbidden": ["BUY", "SELL", "HOLD", "direct_score_override"],
    }
