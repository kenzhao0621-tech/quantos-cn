"""Causal Graph Engine — policy/theme → factor candidate edges (advisory)."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def default_causal_graph() -> dict[str, Any]:
    edges = [
        {
            "source": "AI_policy_support",
            "target": "industry_acceleration",
            "direction": "positive",
            "weight": 0.6,
            "confidence": 0.5,
            "evidence": "rule_template",
            "last_updated": datetime.now().isoformat(timespec="seconds"),
        },
        {
            "source": "industry_acceleration",
            "target": "theme_strength",
            "direction": "positive",
            "weight": 0.5,
            "confidence": 0.4,
            "evidence": "rule_template",
            "last_updated": datetime.now().isoformat(timespec="seconds"),
        },
        {
            "source": "theme_strength",
            "target": "candidate_factor",
            "direction": "positive",
            "weight": 0.3,
            "confidence": 0.3,
            "evidence": "requires_validation",
            "last_updated": datetime.now().isoformat(timespec="seconds"),
        },
        {
            "source": "liquidity_tightening",
            "target": "risk_penalty",
            "direction": "positive",
            "weight": 0.7,
            "confidence": 0.6,
            "evidence": "regime_rule",
            "last_updated": datetime.now().isoformat(timespec="seconds"),
        },
    ]
    return {
        "nodes": ["Policy", "Macro", "Liquidity", "Industry", "Theme", "Company", "Factor", "Risk"],
        "edges": edges,
        "forbidden": ["direct_score_override", "BUY", "SELL"],
    }


def load_causal_graph() -> dict[str, Any]:
    return default_causal_graph()
