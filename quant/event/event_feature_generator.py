"""Event feature generator — disabled until ValidationOS passes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

EVENT_FEATURES: dict[str, dict[str, Any]] = {
    "disclosure_penalty_score": {"enabled": True, "validation_status": "PARTIAL", "note": "wired in screener"},
    "event_momentum_score": {"enabled": False, "validation_status": "NOT_RUN"},
    "policy_event_score": {"enabled": False, "validation_status": "NOT_RUN"},
    "earnings_surprise_score": {"enabled": False, "validation_status": "NOT_RUN"},
}


def generate_event_features(*, limit: int = 20) -> dict[str, Any]:
    from quant.event.event_classifier import classify_disclosure
    from quant.event.event_graph import build_event_graph

    graph = build_event_graph(limit=limit)
    disc_path = ROOT / "data" / "disclosures" / "disclosure_index.json"
    sample_events: list[dict[str, Any]] = []
    if disc_path.exists():
        import json

        raw = json.loads(disc_path.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else raw.get("items") or []
        sample_events = [classify_disclosure(i) for i in items[:5]]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "graph": {"node_count": graph["node_count"], "edge_count": graph["edge_count"]},
        "sample_events": sample_events,
        "candidate_features": EVENT_FEATURES,
        "production_enabled_count": sum(1 for f in EVENT_FEATURES.values() if f.get("enabled")),
        "forbidden": ["BUY", "SELL", "direct_score_override"],
    }
