"""Point-in-time disclosure filtering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PITFilterResult:
    as_of: str
    cutoff: str
    passed: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    reject_reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "cutoff": self.cutoff,
            "passed_count": len(self.passed),
            "rejected_count": len(self.rejected),
            "reject_reasons": self.reject_reasons,
        }


def filter_point_in_time(
    rows: list[dict[str, Any]],
    *,
    analysis_cutoff: str,
    target_trading_date: str = "",
) -> PITFilterResult:
    """Reject disclosures published after analysis cutoff."""
    cutoff = analysis_cutoff.replace("T", " ")[:19]
    if len(cutoff) == 10:
        cutoff += " 23:59:59"
    result = PITFilterResult(as_of=analysis_cutoff[:10], cutoff=cutoff)
    for row in rows:
        pub = str(row.get("official_publication_time") or "")
        if not pub:
            row = {**row, "pit_reject": "missing_publication_time"}
            result.rejected.append(row)
            result.reject_reasons.append(f"missing_pub_time:{row.get('disclosure_id', '')}")
            continue
        pub_norm = pub.replace("T", " ")[:19]
        if pub_norm > cutoff:
            row = {**row, "pit_reject": "future_leakage"}
            result.rejected.append(row)
            result.reject_reasons.append(f"future:{row.get('disclosure_id', '')}")
            continue
        row = {**row, "point_in_time_eligible": True, "target_trading_date": target_trading_date}
        result.passed.append(row)
    return result
