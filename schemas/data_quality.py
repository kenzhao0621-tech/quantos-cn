"""Snapshot data quality checks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class DataQualityResult:
    dataset: str
    passed: bool
    checked_at: str
    row_count: int = 0
    required_fields_present: bool = True
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    data_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_REQUIRED_SPOT = ("code", "name", "price", "change_pct")
_REQUIRED_INDICES = ("sh", "sz")


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if "rows" in payload:
            return list(payload["rows"])
        if "indices" in payload:
            return [{"key": k, **v} if isinstance(v, dict) else {"key": k, "value": v} for k, v in payload["indices"].items()]
    if isinstance(payload, list):
        return payload
    return []


def run_snapshot_quality_checks(
    dataset: str,
    payload: Any,
    *,
    data_hash: str = "",
    min_rows: int = 1,
) -> DataQualityResult:
    """Validate normalized snapshot payload for a dataset."""
    now = datetime.now().isoformat(timespec="seconds")
    warnings: list[str] = []
    errors: list[str] = []
    missing: list[str] = []
    rows = _rows(payload)
    row_count = len(rows)

    if row_count < min_rows:
        errors.append(f"row_count {row_count} < min_rows {min_rows}")

    if dataset == "spot_quotes" and rows:
        sample = rows[0]
        for f in _REQUIRED_SPOT:
            if f not in sample:
                missing.append(f)
        st_count = sum(1 for r in rows if r.get("is_st"))
        if st_count == 0 and row_count > 100:
            warnings.append("no ST flags detected — schema may be incomplete")

    elif dataset == "indices" and isinstance(payload, dict):
        for f in _REQUIRED_INDICES:
            if f not in payload and f not in {k.lower() for k in payload}:
                missing.append(f)

    elif dataset == "trading_calendar":
        days = payload.get("days", []) if isinstance(payload, dict) else payload
        if not days:
            errors.append("trading calendar empty")
        row_count = len(days) if isinstance(days, list) else 0

    passed = not errors and not missing
    return DataQualityResult(
        dataset=dataset,
        passed=passed,
        checked_at=now,
        row_count=row_count,
        required_fields_present=not missing,
        missing_fields=missing,
        warnings=warnings,
        errors=errors,
        data_hash=data_hash,
    )


def summarize_quality(results: list[DataQualityResult]) -> dict[str, Any]:
    return {
        "passed": all(r.passed for r in results),
        "datasets": [r.to_dict() for r in results],
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }
