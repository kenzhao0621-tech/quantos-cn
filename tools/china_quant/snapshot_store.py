"""Persisted market snapshots when live AKShare unavailable."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / ".cache" / "china-quant" / "snapshots"


def save_snapshot(payload: dict[str, Any], label: str = "latest") -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{label}.json"
    path.write_text(json.dumps({
        "saved_at": datetime.now().isoformat(),
        "payload": payload,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_snapshot(label: str = "latest") -> Optional[dict[str, Any]]:
    path = SNAPSHOT_DIR / f"{label}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("payload")
