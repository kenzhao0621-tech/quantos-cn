"""Lightweight agent panel — structured fields only, no free-form chat."""

from __future__ import annotations

from datetime import datetime
from typing import Any

AGENTS = (
    "Policy Analyst",
    "Industry Analyst",
    "Institutional Investor",
    "Retail Sentiment Analyst",
    "Risk Officer",
)


def run_agent_panel(event: dict[str, Any]) -> list[dict[str, Any]]:
    cat = event.get("category", "unknown")
    direction = "neutral"
    risk = "medium"
    if cat in ("policy_support", "buyback", "earnings_positive", "government_subsidy"):
        direction = "positive"
        risk = "low"
    elif cat in ("audit_issue", "regulatory_penalty", "share_reduction", "earnings_negative"):
        direction = "negative"
        risk = "high"

    outputs = []
    for name in AGENTS:
        conf = 0.55 if name == "Risk Officer" else 0.45
        outputs.append({
            "agent_name": name,
            "event_id": event.get("event_id", ""),
            "impact_direction": direction,
            "affected_industries": event.get("industries") or [],
            "risk_level": risk if name == "Risk Officer" else "medium",
            "confidence": conf,
            "reasoning_summary": f"Structured read on {cat} — not a trade signal.",
            "evidence": [event.get("title", "")[:120]],
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "forbidden": ["BUY", "SELL", "HOLD"],
        })
    return outputs
