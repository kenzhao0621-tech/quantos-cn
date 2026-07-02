"""DataTruth validation gates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quant.data_truth_os.contract import DataTruthRecord, QualityLevel
from quant.data_truth_os.registry import get_source


def validate_record(record: DataTruthRecord) -> tuple[bool, list[str]]:
    """Return (ok, missing_fields)."""
    missing: list[str] = []
    for fld in ("source_url", "fetched_at", "updated_at", "data_version", "quality_level"):
        if not getattr(record, fld, None):
            missing.append(fld)
    if record.quality_level in (QualityLevel.UNAVAILABLE.value,):
        missing.append("quality_unavailable")
    return (len(missing) == 0, missing)


def gate_for_advisory(records: list[DataTruthRecord]) -> dict[str, Any]:
    """Summarise data truth for advisory envelope."""
    verified = [r for r in records if r.is_usable_for_verified_facts()]
    degraded = [r for r in records if not r.is_usable_for_verified_facts()]
    return {
        "verified_count": len(verified),
        "degraded_count": len(degraded),
        "records": [r.to_dict() for r in records],
        "all_critical_present": len(verified) > 0,
        "quality_summary": _quality_summary(records),
    }


def _quality_summary(records: list[DataTruthRecord]) -> str:
    if not records:
        return "无数据来源记录"
    levels = {r.quality_level for r in records}
    if QualityLevel.S.value in levels:
        return "含交易所/官方来源"
    if QualityLevel.A.value in levels:
        return "含公开数据商来源"
    if QualityLevel.DEGRADED.value in levels:
        return "部分数据已降级"
    return "数据质量待确认"


def wrap_derived(
    *,
    source_id: str,
    field_name: str,
    value: Any,
    data_version: str,
    updated_at: str | None = None,
    is_estimated: bool = False,
    degraded_reason: str = "",
) -> DataTruthRecord:
    """Build a DataTruthRecord from registry metadata + runtime values."""
    meta = get_source(source_id) or {}
    ql = meta.get("reliability_level", QualityLevel.DEGRADED.value)
    if degraded_reason:
        ql = QualityLevel.DEGRADED.value
    ts = datetime.now().isoformat(timespec="seconds")
    return DataTruthRecord(
        source_name=meta.get("name", source_id),
        source_type=meta.get("source_type", "derived"),
        source_url=meta.get("base_url", ""),
        api_name=meta.get("api_or_page", ""),
        fetched_at=ts,
        updated_at=updated_at or ts,
        data_version=data_version,
        quality_level=ql,
        degraded_reason=degraded_reason,
        is_realtime=bool(meta.get("realtime_capability")),
        is_estimated=is_estimated,
        field_name=field_name,
        value=value,
    )
