"""Event knowledge graph — company/industry/event relations."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def build_event_graph(*, limit: int = 50) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    disc_path = ROOT / "data" / "disclosures" / "disclosure_index.json"
    if disc_path.exists():
        import json

        from quant.event.event_classifier import classify_disclosure

        raw = json.loads(disc_path.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else raw.get("items") or raw.get("disclosures") or []
        for item in items[:limit]:
            ev = classify_disclosure(item)
            sym = ev.get("symbol") or "unknown"
            eid = ev.get("event_id") or f"ev_{sym}_{len(nodes)}"
            nodes.append({"id": eid, "type": "Event", "category": ev["category"]})
            if sym and sym != "unknown":
                nodes.append({"id": sym, "type": "Company"})
                edges.append({"source": eid, "target": sym, "relation": "affects"})
                edges.append({"source": sym, "target": ev["category"], "relation": "correlates_with"})

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes[:limit * 2],
        "edges": edges[:limit * 3],
        "forbidden": ["BUY", "SELL", "direct_score_override"],
    }
