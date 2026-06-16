"""Audit log and distributed tracing helpers."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import GatewayConfig


@dataclass
class TraceContext:
    trace_id: str
    request_id: str
    user_id: str
    project_id: str
    run_id: str = ""
    spans: list[dict[str, Any]] = field(default_factory=list)

    def start_span(self, name: str, **attrs: Any) -> dict[str, Any]:
        span = {
            "span_id": str(uuid.uuid4()),
            "trace_id": self.trace_id,
            "name": name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "attrs": attrs,
        }
        self.spans.append(span)
        return span


class AuditLogger:
    def __init__(self, path: Path | None = None) -> None:
        cfg = GatewayConfig.load()
        self.path = path or cfg.audit_log_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event_type: str, actor: str, detail: dict[str, Any], trace: TraceContext | None = None) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "actor": actor,
            "detail": detail,
            "trace_id": trace.trace_id if trace else "",
            "request_id": trace.request_id if trace else "",
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def read_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = [ln for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines[-limit:]]
