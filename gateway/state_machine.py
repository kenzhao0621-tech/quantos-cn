"""Human-controlled promotion state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TradingMode(str, Enum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    DATA_READY = "DATA_READY"
    PAPER_TRADING = "PAPER_TRADING"
    SHADOW_LIVE = "SHADOW_LIVE"
    LIMITED_LIVE_REVIEW_REQUIRED = "LIMITED_LIVE_REVIEW_REQUIRED"
    HALTED = "HALTED"


ALLOWED_AUTO_TRANSITIONS: dict[TradingMode, set[TradingMode]] = {
    TradingMode.RESEARCH_ONLY: {TradingMode.DATA_READY, TradingMode.HALTED},
    TradingMode.DATA_READY: {TradingMode.PAPER_TRADING, TradingMode.HALTED},
    TradingMode.PAPER_TRADING: {TradingMode.SHADOW_LIVE, TradingMode.HALTED},
    TradingMode.SHADOW_LIVE: {TradingMode.HALTED},
    TradingMode.LIMITED_LIVE_REVIEW_REQUIRED: {TradingMode.HALTED},
    TradingMode.HALTED: set(),
}

FORBIDDEN_AUTO = {(TradingMode.SHADOW_LIVE, TradingMode.LIMITED_LIVE_REVIEW_REQUIRED)}


@dataclass
class TransitionResult:
    ok: bool
    from_mode: str
    to_mode: str
    reason: str = ""


@dataclass
class StateMachine:
    mode: TradingMode = TradingMode.RESEARCH_ONLY
    history: list[dict[str, str]] = field(default_factory=list)

    def can_transition(self, target: TradingMode) -> TransitionResult:
        if target == TradingMode.HALTED:
            return TransitionResult(True, self.mode.value, target.value, "halt always allowed")
        allowed = ALLOWED_AUTO_TRANSITIONS.get(self.mode, set())
        if target not in allowed:
            return TransitionResult(
                False, self.mode.value, target.value,
                f"transition {self.mode.value} -> {target.value} not allowed automatically",
            )
        if (self.mode, target) in FORBIDDEN_AUTO:
            return TransitionResult(False, self.mode.value, target.value, "forbidden transition")
        return TransitionResult(True, self.mode.value, target.value)

    def transition(self, target: TradingMode, actor: str = "system") -> TransitionResult:
        check = self.can_transition(target)
        if not check.ok:
            return check
        prev = self.mode
        self.mode = target
        self.history.append({"from": prev.value, "to": target.value, "actor": actor})
        return check

    def halt(self, actor: str = "kill_switch") -> TransitionResult:
        prev = self.mode
        self.mode = TradingMode.HALTED
        self.history.append({"from": prev.value, "to": TradingMode.HALTED.value, "actor": actor})
        return TransitionResult(True, prev.value, TradingMode.HALTED.value, "halted")

    def allows_execution(self) -> bool:
        return self.mode in {TradingMode.PAPER_TRADING, TradingMode.SHADOW_LIVE}

    def allows_research(self) -> bool:
        return self.mode != TradingMode.HALTED

    def max_autonomous_label(self) -> str:
        if self.mode == TradingMode.SHADOW_LIVE:
            return "AUTONOMOUS_SHADOW_LIVE"
        if self.mode == TradingMode.PAPER_TRADING:
            return "AUTONOMOUS_PAPER_TRADING"
        return "RESEARCH_ONLY"
