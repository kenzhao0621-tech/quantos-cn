"""Official disclosure ingestion and coverage."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DISC_ROOT = ROOT / "data" / "disclosures"


def persist_disclosures(rows: list[dict[str, Any]], *, provider: str, run_id: str = "") -> dict[str, Any]:
    DISC_ROOT.mkdir(parents=True, exist_ok=True)
    path = DISC_ROOT / f"disclosures_{provider}.json"
    payload = {
        "provider": provider,
        "run_id": run_id,
        "row_count": len(rows),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "rows": rows[:2000],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path.relative_to(ROOT)), "row_count": len(rows), "provider": provider}


def disclosure_coverage_report() -> dict[str, Any]:
    files = list(DISC_ROOT.glob("*.json")) if DISC_ROOT.exists() else []
    total = sum(json.loads(f.read_text())["row_count"] for f in files) if files else 0
    return {
        "file_count": len(files),
        "total_rows": total,
        "status": "unavailable" if total == 0 else "partial",
        "candidate_gate": total >= 50,
    }
