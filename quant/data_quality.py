"""Provider-aware snapshot data quality checks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

DEFAULT_MIN_ROWS = 5000


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
    provider: str = ""
    source_dataset: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_REQUIRED_SPOT = ("code", "name", "price", "change_pct")


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if "rows" in payload:
            return list(payload["rows"])
    if isinstance(payload, list):
        return payload
    return []


def run_snapshot_quality_checks(
    dataset: str,
    payload: Any,
    *,
    data_hash: str = "",
    min_rows: int = DEFAULT_MIN_ROWS,
    provider: str = "",
    source_dataset: str = "",
    doc_meta: Optional[dict[str, Any]] = None,
) -> DataQualityResult:
    now = datetime.now().isoformat(timespec="seconds")
    warnings: list[str] = []
    errors: list[str] = []
    missing: list[str] = []
    rows = _rows(payload)
    row_count = len(rows)
    meta = doc_meta or {}

    if meta.get("is_fixture"):
        errors.append("fixture contamination")
    if meta.get("is_manual") and meta.get("require_non_fixture"):
        errors.append("manual contamination when disallowed")

    if dataset == "spot_quotes":
        if row_count < min_rows:
            errors.append(f"row_count {row_count} < min_rows {min_rows}")
        if rows:
            sample = rows[0]
            for f in _REQUIRED_SPOT:
                if f not in sample:
                    missing.append(f)
            dup = row_count - len({r.get("code") for r in rows})
            if dup > row_count * 0.001:
                errors.append(f"duplicate symbols: {dup}")
            valid_price = sum(1 for r in rows if r.get("price", 0) > 0)
            if valid_price / max(row_count, 1) < 0.95:
                errors.append("valid_price_ratio below 0.95")
            dates = {r.get("market_date") for r in rows if r.get("market_date")}
            if len(dates) > 1:
                errors.append("mixed market dates")
        if source_dataset == "stock_zh_a_spot" and meta.get("freshness") == "SOURCE_LATEST_TIMESTAMP_UNCONFIRMED":
            warnings.append("exact source timestamp unconfirmed")

    elif dataset == "trading_calendar":
        days = payload.get("days", []) if isinstance(payload, dict) else payload
        if not days:
            errors.append("trading calendar empty")
        row_count = len(days) if isinstance(days, list) else 0

    elif dataset == "indices" and isinstance(payload, dict):
        if "sh" not in payload:
            missing.append("sh")

    passed = not errors and not missing
    return DataQualityResult(
        dataset=dataset, passed=passed, checked_at=now, row_count=row_count,
        required_fields_present=not missing, missing_fields=missing,
        warnings=warnings, errors=errors, data_hash=data_hash,
        provider=provider, source_dataset=source_dataset,
    )
