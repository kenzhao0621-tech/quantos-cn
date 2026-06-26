"""Scenario Tree Engine — structured what-if (not trade probability)."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def build_scenario_tree(event: str, *, industries: list[str] | None = None) -> dict[str, Any]:
    inds = industries or ["Technology", "Manufacturing"]
    return {
        "event": event,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": "probability_estimate 是情景权重，不是交易概率",
        "scenarios": [
            {
                "name": "strong_policy_follow_through",
                "probability_estimate": 0.35,
                "affected_industries": inds,
                "expected_state_transition": "theme_driven",
                "confidence": 0.4,
            },
            {
                "name": "limited_market_impact",
                "probability_estimate": 0.45,
                "affected_industries": inds,
                "expected_state_transition": "sideways",
                "confidence": 0.5,
            },
            {
                "name": "sell_the_news",
                "probability_estimate": 0.20,
                "affected_industries": inds,
                "expected_state_transition": "mean_reversion",
                "confidence": 0.35,
            },
        ],
        "forbidden": ["BUY", "SELL", "target_price"],
    }
