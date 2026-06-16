"""Standard API response envelope."""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    ok: bool
    data: Optional[T] = None
    error: Optional[dict[str, Any]] = None
    meta: dict[str, Any] = Field(default_factory=dict)


def envelope_ok(data: Any, **meta: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None, "meta": meta}


def envelope_err(code: str, message: str, **meta: Any) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}, "meta": meta}
