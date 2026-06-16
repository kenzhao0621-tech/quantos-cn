"""Disclosure-specific candidate readiness evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quant.disclosures.protocol import DisclosureStatus


@dataclass
class DisclosureReadiness:
    state: str
    query_completed: bool
    provider: str
    provider_status: str
    row_count: int
    verified_zero_results: bool
    blocking_events: list[dict[str, Any]] = field(default_factory=list)
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.state in {"PASS_WITH_DISCLOSURES", "PASS_WITH_VERIFIED_ZERO_RESULTS"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "query_completed": self.query_completed,
            "provider": self.provider,
            "provider_status": self.provider_status,
            "row_count": self.row_count,
            "verified_zero_results": self.verified_zero_results,
            "passed": self.passed,
            "blocking_events": self.blocking_events,
            "detail": self.detail,
        }


def evaluate_disclosure_readiness(meta: dict[str, Any]) -> DisclosureReadiness:
    """Distinguish verified zero results from unavailable provider."""
    status = meta.get("primary_status", "")
    query_state = meta.get("query_state", "")
    row_count = int(meta.get("row_count", 0) or 0)
    provider = meta.get("primary_provider", "")

    completed = status in {
        DisclosureStatus.SUCCESS_WITH_ROWS.value,
        DisclosureStatus.SUCCESS_ZERO_RESULTS.value,
    } or query_state.startswith("DISCLOSURE_QUERY_COMPLETE")

    if not completed:
        return DisclosureReadiness(
            state="BLOCKED_PROVIDER_UNAVAILABLE",
            query_completed=False,
            provider=provider,
            provider_status=status,
            row_count=row_count,
            verified_zero_results=False,
            detail=query_state or status or "provider not queried",
        )

    if meta.get("verified_zero_results") or row_count == 0:
        return DisclosureReadiness(
            state="PASS_WITH_VERIFIED_ZERO_RESULTS",
            query_completed=True,
            provider=provider,
            provider_status=status,
            row_count=0,
            verified_zero_results=True,
            detail="official query completed with zero announcements in window",
        )

    blocking = [r for r in meta.get("rows", []) if r.get("blocking_status") == "BLOCKING_IF_ACTIVE"]
    if blocking:
        return DisclosureReadiness(
            state="BLOCKED_CRITICAL_DISCLOSURE",
            query_completed=True,
            provider=provider,
            provider_status=status,
            row_count=row_count,
            verified_zero_results=False,
            blocking_events=blocking[:20],
            detail=f"{len(blocking)} blocking-category disclosures",
        )

    return DisclosureReadiness(
        state="PASS_WITH_DISCLOSURES",
        query_completed=True,
        provider=provider,
        provider_status=status,
        row_count=row_count,
        verified_zero_results=False,
        detail=f"{row_count} disclosures ingested",
    )
