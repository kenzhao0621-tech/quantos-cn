"""Shared V2 adapter helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quant.freshness_contract import FreshnessClass, FreshnessValidationResult, validate_freshness
from quant.provider_base_v2 import ProviderCapabilities, ProviderHealth
from quant.provider_result import ProviderResult, ProviderStatus


def default_capabilities(
    name: str,
    *,
    datasets: dict[str, str],
    requires_credentials: bool = False,
    intraday: bool = False,
    eod: bool = True,
    historical: bool = False,
    warnings: tuple[str, ...] = (),
) -> ProviderCapabilities:
    return ProviderCapabilities(
        provider_name=name,
        datasets=datasets,
        supports_intraday=intraday,
        supports_end_of_day=eod,
        supports_historical=historical,
        requires_credentials=requires_credentials,
        account_permissions_known=False,
        warnings=warnings,
    )


def health_from_fetch(
    name: str,
    *,
    configured: bool,
    probe_live: bool,
    fetch_fn,
    dataset: str = "trading_calendar",
) -> ProviderHealth:
    now = datetime.now()
    if not configured:
        return ProviderHealth(
            provider_name=name, configured=False, reachable=False, authenticated=None,
            status="NOT_CONFIGURED", latency_ms=None, capabilities=None,
            last_error_class="NOT_CONFIGURED", last_error_message="credentials missing",
            checked_at=now,
        )
    if not probe_live:
        return ProviderHealth(
            provider_name=name, configured=True, reachable=True, authenticated=None,
            status="READY", latency_ms=None, capabilities=None,
            last_error_class=None, last_error_message=None, checked_at=now,
        )
    result = fetch_fn(dataset)
    ok = result.ok
    return ProviderHealth(
        provider_name=name, configured=True, reachable=ok, authenticated=ok,
        status=result.status.value, latency_ms=result.elapsed_ms, capabilities=None,
        last_error_class=None if ok else result.status.value,
        last_error_message=result.error, checked_at=now,
    )


def default_freshness_validate(
    dataset: str,
    result: ProviderResult,
    *,
    sla_key: str,
    require_live: bool = False,
    latest_completed_trade_date: str = "",
) -> FreshnessValidationResult:
    if not result.ok:
        return FreshnessValidationResult(False, FreshnessClass.STALE.value, result.error or "fetch failed", blocked=True)
    fc = result.freshness or FreshnessClass.SOURCE_LATEST_TIMESTAMP_UNCONFIRMED.value
    evt = ""
    if isinstance(result.payload, dict):
        evt = result.payload.get("source_event_time") or result.payload.get("retrieved_at", result.retrieved_at)
    return validate_freshness(
        dataset_sla_key=sla_key,
        freshness_class=fc,
        source_event_time=evt or result.retrieved_at,
        market_date=result.market_date,
        require_live=require_live,
        latest_completed_trade_date=latest_completed_trade_date,
    )


def basic_quality(dataset: str, payload: Any, *, min_rows: int = 1) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if dataset == "spot_quotes":
        rows = payload.get("rows", []) if isinstance(payload, dict) else []
        if len(rows) < min_rows:
            errors.append(f"row_count {len(rows)} < {min_rows}")
    elif dataset == "index_daily":
        bars = payload.get("bars", {}) if isinstance(payload, dict) else {}
        if not bars:
            errors.append("no index bars")
    return not errors, errors
