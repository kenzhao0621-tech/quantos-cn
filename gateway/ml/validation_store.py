"""Persist model validation runs for the model lab history panel."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from gateway.config import ROOT

VALIDATIONS_PATH = ROOT / "data" / "gateway" / "model_validations.jsonl"


def append_validation(result: dict[str, Any]) -> dict[str, Any]:
    record = {
        "validation_id": str(uuid4())[:12],
        "created_at": datetime.now(timezone.utc).isoformat(),
        **result,
    }
    VALIDATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with VALIDATIONS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def list_validations(limit: int = 30) -> list[dict[str, Any]]:
    if not VALIDATIONS_PATH.exists():
        return []
    rows = []
    for line in VALIDATIONS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:][::-1]
