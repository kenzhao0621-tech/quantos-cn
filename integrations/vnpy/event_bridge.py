"""vn.py → Gateway event bridge."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from integrations.vnpy.events import EventType, QuantOSEvent

ROOT = Path(__file__).resolve().parents[2]
EVENT_LOG = ROOT / "data" / "quantos" / "events.jsonl"


class EventBridge:
    """Translates vn.py-style events to QuantOS unified events and Gateway audit stream."""

    def __init__(self, max_buffer: int = 5000) -> None:
        self._handlers: list[Callable[[QuantOSEvent], None]] = []
        self._buffer: deque[QuantOSEvent] = deque(maxlen=max_buffer)
        EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)

    def register(self, handler: Callable[[QuantOSEvent], None]) -> None:
        self._handlers.append(handler)

    def emit(self, event: QuantOSEvent) -> None:
        event.ingest_time = datetime.now(timezone.utc).isoformat()
        self._buffer.append(event)
        with EVENT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        for h in self._handlers:
            h(event)

    def emit_order(self, *, run_id: str, order: dict[str, Any], strategy_id: str = "") -> QuantOSEvent:
        ev = QuantOSEvent(
            event_type=EventType.ORDER,
            source="vnpy_bridge",
            run_id=run_id,
            strategy_id=strategy_id,
            payload=order,
        )
        self.emit(ev)
        return ev

    def emit_trade(self, *, run_id: str, trade: dict[str, Any], strategy_id: str = "") -> QuantOSEvent:
        ev = QuantOSEvent(
            event_type=EventType.TRADE,
            source="vnpy_bridge",
            run_id=run_id,
            strategy_id=strategy_id,
            payload=trade,
        )
        self.emit(ev)
        return ev

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return [e.to_dict() for e in list(self._buffer)[-limit:]]

    def dedupe_check(self, event_id: str) -> bool:
        return any(e.event_id == event_id for e in self._buffer)
