"""Point-in-time integrity checks for research and backtest inputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class PointInTimeCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class PointInTimeReport:
    as_of_date: str
    checks: list[PointInTimeCheck] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["checks"] = [asdict(c) for c in self.checks]
        return d


def evaluate_point_in_time_integrity(
    *,
    as_of_date: str,
    snapshot_market_date: Optional[str] = None,
    uses_future_bars: bool = False,
    fundamentals_lag_days: int = 0,
) -> PointInTimeReport:
    checks: list[PointInTimeCheck] = []
    checks.append(PointInTimeCheck(
        "as_of_date_present", bool(as_of_date), as_of_date or "missing",
    ))
    if snapshot_market_date:
        snap = snapshot_market_date.replace("-", "")
        asof = as_of_date.replace("-", "")
        checks.append(PointInTimeCheck(
            "snapshot_not_after_as_of",
            snap <= asof,
            f"snapshot={snapshot_market_date} as_of={as_of_date}",
        ))
    checks.append(PointInTimeCheck(
        "no_future_bars", not uses_future_bars, "lookahead" if uses_future_bars else "ok",
    ))
    checks.append(PointInTimeCheck(
        "fundamentals_lag_acknowledged",
        fundamentals_lag_days >= 0,
        f"lag_days={fundamentals_lag_days}",
    ))
    passed = all(c.passed for c in checks)
    return PointInTimeReport(as_of_date=as_of_date, checks=checks, passed=passed)
