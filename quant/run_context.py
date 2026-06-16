"""Run ID context for fetch/validate binding."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

_current_run_id: str | None = None


def new_run_id() -> str:
    global _current_run_id
    _current_run_id = f"{datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
    return _current_run_id


def get_run_id() -> str | None:
    return _current_run_id


def set_run_id(run_id: str) -> None:
    global _current_run_id
    _current_run_id = run_id
