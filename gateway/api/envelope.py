"""Standard API response envelope."""

from __future__ import annotations

import uuid
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    ok: bool
    data: Optional[T] = None
    error: Optional[dict[str, Any]] = None
    meta: dict[str, Any] = Field(default_factory=dict)


def _ids(request_id: str = "", trace_id: str = "", run_id: str = "") -> dict[str, str]:
    return {
        "request_id": request_id or str(uuid.uuid4()),
        "trace_id": trace_id or str(uuid.uuid4()),
        **({"run_id": run_id} if run_id else {}),
    }


def envelope_ok(
    data: Any,
    *,
    request_id: str = "",
    trace_id: str = "",
    run_id: str = "",
    artifact_path: str = "",
    provenance: dict[str, Any] | None = None,
    **meta: Any,
) -> dict[str, Any]:
    ids = _ids(request_id, trace_id, run_id)
    prov = provenance or {}
    if artifact_path:
        prov["artifact_path"] = artifact_path
    return {
        "ok": True,
        "status": "succeeded",
        "data": data,
        "error": None,
        "errors": [],
        "provenance": prov,
        "meta": {**ids, **meta},
        "request_id": ids["request_id"],
        "trace_id": ids["trace_id"],
        **({"run_id": run_id} if run_id else {}),
    }


def envelope_err(
    code: str,
    message: str,
    *,
    request_id: str = "",
    trace_id: str = "",
    run_id: str = "",
    **meta: Any,
) -> dict[str, Any]:
    ids = _ids(request_id, trace_id, run_id)
    return {
        "ok": False,
        "status": "failed",
        "data": None,
        "error": {"code": code, "message": message},
        "errors": [{"code": code, "message": message}],
        "provenance": {},
        "meta": {**ids, **meta},
        "request_id": ids["request_id"],
        "trace_id": ids["trace_id"],
        **({"run_id": run_id} if run_id else {}),
    }
