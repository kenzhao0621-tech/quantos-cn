"""Append-only closed-loop implementation ledger."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "ai" / "final" / "CLOSED_LOOP_LEDGER.jsonl"


def append_step(
    step_id: str,
    objective: str,
    *,
    precondition: str = "",
    files_changed: list[str] | None = None,
    test_ids: list[str] | None = None,
    expected: str = "",
    actual: str = "",
    artifacts: list[str] | None = None,
    failure: str = "",
    repair: str = "",
    rerun_result: str = "",
    commit_state: str = "",
) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "step_id": step_id,
        "objective": objective,
        "precondition": precondition,
        "files_changed": files_changed or [],
        "test_ids": test_ids or [],
        "expected": expected,
        "actual": actual,
        "artifacts": artifacts or [],
        "failure": failure,
        "repair": repair,
        "rerun_result": rerun_result,
        "commit_state": commit_state,
    }
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
