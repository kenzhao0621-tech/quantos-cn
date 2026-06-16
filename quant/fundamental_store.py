"""Fundamental snapshot persistence and coverage."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FUND_ROOT = ROOT / "data" / "fundamentals"


def persist_fundamentals(rows: list[dict[str, Any]], *, provider: str, run_id: str = "") -> dict[str, Any]:
    FUND_ROOT.mkdir(parents=True, exist_ok=True)
    path = FUND_ROOT / f"fundamentals_{provider}.json"
    payload = {
        "provider": provider,
        "run_id": run_id,
        "row_count": len(rows),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "rows": rows[:5000],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path.relative_to(ROOT)), "row_count": len(rows), "provider": provider}


def fundamental_coverage_report() -> dict[str, Any]:
    files = list(FUND_ROOT.glob("*.json")) if FUND_ROOT.exists() else []
    total = sum(json.loads(f.read_text())["row_count"] for f in files) if files else 0
    return {
        "file_count": len(files),
        "total_rows": total,
        "status": "unavailable" if total == 0 else "partial",
        "candidate_gate": total >= 1000,
    }
