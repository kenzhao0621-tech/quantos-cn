"""Kill switch and halt controls."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT


@dataclass
class KillSwitchState:
    state: str = "OPEN"  # OPEN | HALTED
    reason: str = ""
    halted_at: str = ""
    halted_by: str = ""
    reset_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "halted_at": self.halted_at,
            "halted_by": self.halted_by,
            "reset_requested": self.reset_requested,
        }


class KillSwitch:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or ROOT / "data" / "gateway" / "kill_switch.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    def _load(self) -> KillSwitchState:
        if not self.path.exists():
            return KillSwitchState()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return KillSwitchState(**raw)

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._state.to_dict(), indent=2), encoding="utf-8")

    @property
    def is_halted(self) -> bool:
        return self._state.state == "HALTED"

    def halt(self, reason: str, actor: str) -> KillSwitchState:
        self._state = KillSwitchState(
            state="HALTED",
            reason=reason,
            halted_at=datetime.now(timezone.utc).isoformat(),
            halted_by=actor,
            reset_requested=False,
        )
        self._save()
        return self._state

    def request_reset(self, actor: str) -> KillSwitchState:
        if not self.is_halted:
            return self._state
        self._state.reset_requested = True
        self._state.reason = f"{self._state.reason}; reset requested by {actor}"
        self._save()
        return self._state

    def manual_reset(self, actor: str) -> KillSwitchState:
        """Human-only reset — not callable by autonomous paths."""
        self._state = KillSwitchState(state="OPEN", reason=f"reset by {actor}")
        self._save()
        return self._state

    def status(self) -> dict[str, Any]:
        return self._state.to_dict()
