"""Unified QuantOS event envelope — vn.py compatible semantics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class EventType(str, Enum):
    TICK = "TickEvent"
    BAR = "BarEvent"
    ORDER = "OrderEvent"
    TRADE = "TradeEvent"
    POSITION = "PositionEvent"
    ACCOUNT = "AccountEvent"
    CONTRACT = "ContractEvent"
    LOG = "LogEvent"
    RISK = "RiskEvent"


@dataclass
class QuantOSEvent:
    event_type: EventType
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    request_id: str = ""
    trace_id: str = ""
    run_id: str = ""
    event_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    receive_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ingest_time: str = ""
    account_mask: str = "PAPER"
    strategy_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    @classmethod
    def from_vnpy_like(cls, event_type: str, data: dict[str, Any], *, source: str = "vnpy") -> QuantOSEvent:
        mapping = {
            "eTick.": EventType.TICK,
            "eBar.": EventType.BAR,
            "eOrder.": EventType.ORDER,
            "eTrade.": EventType.TRADE,
            "ePosition.": EventType.POSITION,
            "eAccount.": EventType.ACCOUNT,
            "eContract.": EventType.CONTRACT,
            "eLog.": EventType.LOG,
        }
        et = EventType.LOG
        for k, v in mapping.items():
            if k in event_type or event_type == v.value:
                et = v
                break
        return cls(event_type=et, source=source, payload=data)
