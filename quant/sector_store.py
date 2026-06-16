"""Sector board persistence and coverage reporting."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SECTOR_ROOT = ROOT / "data" / "sectors"


def persist_sector_boards(rows: list[dict[str, Any]], *, provider: str, run_id: str = "") -> dict[str, Any]:
    SECTOR_ROOT.mkdir(parents=True, exist_ok=True)
    path = SECTOR_ROOT / f"sector_boards_{provider}.json"
    payload = {
        "provider": provider,
        "run_id": run_id,
        "row_count": len(rows),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path.relative_to(ROOT)), "row_count": len(rows), "provider": provider}


def sector_coverage_report() -> dict[str, Any]:
    files = list(SECTOR_ROOT.glob("*.json")) if SECTOR_ROOT.exists() else []
    total_rows = 0
    providers: list[str] = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        total_rows += int(data.get("row_count", 0))
        providers.append(str(data.get("provider", "")))
    return {
        "file_count": len(files),
        "total_rows": total_rows,
        "providers": providers,
        "candidate_gate": total_rows >= 30,
        "status": "partial" if total_rows < 30 else "acceptable",
    }
