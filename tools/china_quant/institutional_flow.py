"""Institutional flow — public disclosures only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FlowSignal:
    code: str
    signal_type: str
    value: str
    disclosure_level: str  # confirmed | public_disclosure | inferred | proxy | unavailable
    source: str
    timestamp: str


def parse_institutional_payload(data: dict[str, Any]) -> list[FlowSignal]:
    return [
        FlowSignal(
            code=s["code"],
            signal_type=s["type"],
            value=s.get("value", ""),
            disclosure_level=s.get("level", "public_disclosure"),
            source=s.get("source", "fixture"),
            timestamp=s.get("timestamp", ""),
        )
        for s in data.get("signals", [])
    ]


def signals_for_code(signals: list[FlowSignal], code: str) -> list[FlowSignal]:
    return [s for s in signals if s.code == code]
