"""DataTruthOS contract and gate tests."""

from __future__ import annotations

from quant.data_truth_os import (
    DataTruthRecord,
    QualityLevel,
    gate_for_advisory,
    validate_record,
    wrap_derived,
)


def test_validate_record_requires_provenance_fields():
    rec = DataTruthRecord(
        source_name="test",
        source_type="derived",
        source_url="",
        fetched_at="2026-07-01T10:00:00",
        updated_at="2026-07-01",
        data_version="dv1",
        quality_level=QualityLevel.A.value,
    )
    ok, missing = validate_record(rec)
    assert not ok
    assert "source_url" in missing


def test_usable_for_verified_facts_rejects_degraded():
    rec = DataTruthRecord.now_fetched(
        source_name="SSE",
        source_type="exchange",
        source_url="https://www.sse.com.cn",
        data_version="2026-07-01",
        quality_level=QualityLevel.DEGRADED.value,
        degraded_reason="stale_fallback",
    )
    assert not rec.is_usable_for_verified_facts()


def test_wrap_derived_uses_registry_metadata():
    rec = wrap_derived(
        source_id="tushare_pro",
        field_name="daily_bars",
        value="600519.SH",
        data_version="2026-07-01",
        updated_at="2026-07-01",
    )
    assert rec.source_url
    assert rec.fetched_at
    assert rec.quality_level in {QualityLevel.A.value, QualityLevel.S.value}


def test_gate_for_advisory_summarises_records():
    verified = wrap_derived(
        source_id="tushare_pro",
        field_name="daily_bars",
        value="600519.SH",
        data_version="2026-07-01",
        updated_at="2026-07-01",
    )
    degraded = wrap_derived(
        source_id="kronos_mini",
        field_name="kronos_forecast",
        value=0.02,
        data_version="2026-07-01",
        updated_at="2026-07-01",
        degraded_reason="sidecar_unavailable",
    )
    summary = gate_for_advisory([verified, degraded])
    assert summary["verified_count"] >= 1
    assert summary["degraded_count"] >= 1
    assert summary["records"]
