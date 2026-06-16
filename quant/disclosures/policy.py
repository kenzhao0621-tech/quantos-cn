"""Deterministic disclosure risk policy — LLM summarizes, rules decide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


BLOCKING_CATEGORIES = {
    "SUSPENSION", "DELISTING_RISK", "REGULATORY_ACTION", "RISK_WARNING",
}

POLICY_RULES = [
    {"rule_id": "R001", "effective_from": "2026-01-01", "severity": "HIGH", "blocking_status": "BLOCKING", "category": "SUSPENSION", "reason": "active suspension"},
    {"rule_id": "R002", "effective_from": "2026-01-01", "severity": "HIGH", "blocking_status": "BLOCKING", "category": "DELISTING_RISK", "reason": "delisting risk notice"},
    {"rule_id": "R003", "effective_from": "2026-01-01", "severity": "HIGH", "blocking_status": "BLOCKING", "category": "REGULATORY_ACTION", "reason": "material regulatory action"},
    {"rule_id": "R004", "effective_from": "2026-01-01", "severity": "HIGH", "blocking_status": "BLOCKING", "category": "RISK_WARNING", "reason": "critical risk warning"},
    {"rule_id": "R005", "effective_from": "2026-01-01", "severity": "MEDIUM", "blocking_status": "WARNING", "category": "LITIGATION", "reason": "litigation — review required"},
]


@dataclass
class PolicyEvaluation:
    symbol: str
    blocking_events: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    blocked: bool
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "blocked": self.blocked,
            "state": self.state,
            "blocking_events": self.blocking_events,
            "warnings": self.warnings,
        }


def evaluate_symbol_disclosures(symbol: str, rows: list[dict[str, Any]]) -> PolicyEvaluation:
    sym_rows = [r for r in rows if r.get("stock_code") == symbol.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")]
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for r in sym_rows:
        cat = r.get("category", "")
        if cat in BLOCKING_CATEGORIES:
            blocking.append({**r, "rule_id": _rule_for(cat)})
        elif cat == "LITIGATION":
            warnings.append(r)
    blocked = len(blocking) > 0
    if blocked:
        state = "BLOCKED_CRITICAL_DISCLOSURE"
    elif any(r.get("category") == "UNKNOWN_REQUIRES_REVIEW" for r in sym_rows):
        state = "BLOCKED_PARSE_UNRESOLVED"
    else:
        state = "PASS_WITH_DISCLOSURES" if sym_rows else "PASS_WITH_VERIFIED_ZERO_RESULTS"
    return PolicyEvaluation(symbol=symbol, blocking_events=blocking, warnings=warnings, blocked=blocked, state=state)


def _rule_for(category: str) -> str:
    for r in POLICY_RULES:
        if r["category"] == category:
            return r["rule_id"]
    return "R000"
