"""Freshness classes, SLA validation, and provenance contract — V2."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any, Optional
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")

FRESHNESS_SLA: dict[str, Any] = {
    "live_spot": {"during_open_session_max_age_seconds": 30, "outside_open_session": "latest_verified_session_close"},
    "minute_bars": {"during_open_session_max_age_seconds": 120},
    "major_indices_live": {"during_open_session_max_age_seconds": 30},
    "daily_bars": {"freshness": "latest_completed_trading_day"},
    "fundamentals": {"freshness": "latest_officially_published_record"},
    "official_disclosures": {"freshness": "latest_successful_official_poll"},
    "sector_membership": {"freshness": "latest_provider_update_with_effective_date"},
    "historical_bars": {"freshness": "complete_through_latest_completed_trading_day"},
}


class FreshnessClass(str, Enum):
    EXCHANGE_REALTIME = "EXCHANGE_REALTIME"
    LICENSED_REALTIME = "LICENSED_REALTIME"
    BROKER_REALTIME = "BROKER_REALTIME"
    PROVIDER_REALTIME = "PROVIDER_REALTIME"
    SOURCE_LATEST_TIMESTAMP_CONFIRMED = "SOURCE_LATEST_TIMESTAMP_CONFIRMED"
    SOURCE_LATEST_TIMESTAMP_UNCONFIRMED = "SOURCE_LATEST_TIMESTAMP_UNCONFIRMED"
    DELAYED_INTRADAY = "DELAYED_INTRADAY"
    END_OF_DAY = "END_OF_DAY"
    HISTORICAL = "HISTORICAL"
    MANUAL_IMPORT = "MANUAL_IMPORT"
    STALE = "STALE"
    FIXTURE = "FIXTURE"


LIVE_CLASSES = frozenset({
    FreshnessClass.EXCHANGE_REALTIME,
    FreshnessClass.LICENSED_REALTIME,
    FreshnessClass.BROKER_REALTIME,
    FreshnessClass.PROVIDER_REALTIME,
    FreshnessClass.SOURCE_LATEST_TIMESTAMP_CONFIRMED,
})


@dataclass
class ProvenanceRecord:
    source_event_time: str = ""
    provider_received_time: str = ""
    system_ingested_time: str = ""
    exchange_timezone: str = "Asia/Shanghai"
    freshness_class: str = FreshnessClass.SOURCE_LATEST_TIMESTAMP_UNCONFIRMED.value
    measured_latency_ms: float = 0.0
    maximum_acceptable_age_seconds: int = 30
    market_session: str = "unknown"
    is_current_for_requested_mode: bool = False
    market_date: str = ""
    endpoint: str = ""
    source_dataset: str = ""
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FreshnessValidationResult:
    passed: bool
    freshness_class: str
    reason: str = ""
    blocked: bool = False
    provenance: Optional[ProvenanceRecord] = None

    def to_dict(self) -> dict[str, Any]:
        d = {"passed": self.passed, "freshness_class": self.freshness_class, "reason": self.reason, "blocked": self.blocked}
        if self.provenance:
            d["provenance"] = self.provenance.to_dict()
        return d


def market_session_status(now: Optional[datetime] = None) -> tuple[str, bool]:
    """Return (session_label, is_open). A-share regular session approximation."""
    now = now or datetime.now(CST)
    if now.weekday() >= 5:
        return "closed_weekend", False
    t = now.time()
    morning = time(9, 30) <= t <= time(11, 30)
    afternoon = time(13, 0) <= t <= time(15, 0)
    if morning:
        return "open_morning", True
    if afternoon:
        return "open_afternoon", True
    if time(9, 15) <= t < time(9, 30):
        return "pre_open", False
    if time(11, 30) < t < time(13, 0):
        return "lunch_break", False
    return "closed", False


def _parse_ts(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(ts[:19], fmt)
            return dt.replace(tzinfo=CST)
        except ValueError:
            continue
    return None


def validate_freshness(
    *,
    dataset_sla_key: str,
    freshness_class: str,
    source_event_time: str = "",
    market_date: str = "",
    require_live: bool = False,
    latest_completed_trade_date: str = "",
    now: Optional[datetime] = None,
) -> FreshnessValidationResult:
    """Fail closed when freshness cannot be proven for the requested mode."""
    now = now or datetime.now(CST)
    session, is_open = market_session_status(now)
    sla = FRESHNESS_SLA.get(dataset_sla_key, {})
    fc = freshness_class

    if fc in (FreshnessClass.FIXTURE.value, FreshnessClass.MANUAL_IMPORT.value):
        return FreshnessValidationResult(False, fc, "fixture/manual cannot satisfy live gate", blocked=True)

    if fc == FreshnessClass.STALE.value:
        return FreshnessValidationResult(False, fc, "explicitly stale", blocked=True)

    if require_live and fc not in {c.value for c in LIVE_CLASSES}:
        if fc == FreshnessClass.END_OF_DAY.value:
            return FreshnessValidationResult(False, fc, "END_OF_DAY rejected for live request", blocked=True)
        if fc == FreshnessClass.SOURCE_LATEST_TIMESTAMP_UNCONFIRMED.value:
            return FreshnessValidationResult(False, fc, "timestamp unconfirmed — BLOCKED_BY_DATA", blocked=True)
        return FreshnessValidationResult(False, fc, f"{fc} not a live class", blocked=True)

    if dataset_sla_key in ("live_spot", "major_indices_live", "minute_bars") and is_open:
        max_age = sla.get("during_open_session_max_age_seconds", 30)
        evt = _parse_ts(source_event_time)
        if not evt and fc == FreshnessClass.SOURCE_LATEST_TIMESTAMP_UNCONFIRMED.value:
            return FreshnessValidationResult(False, fc, "missing event timestamp during open session", blocked=True)
        if evt:
            age = (now - evt).total_seconds()
            if age > max_age:
                return FreshnessValidationResult(False, FreshnessClass.STALE.value, f"age {age:.0f}s > SLA {max_age}s", blocked=True)

    if dataset_sla_key == "daily_bars" and latest_completed_trade_date and market_date:
        if market_date < latest_completed_trade_date:
            return FreshnessValidationResult(False, FreshnessClass.STALE.value, "market_date behind latest completed", blocked=True)

    prov = ProvenanceRecord(
        source_event_time=source_event_time,
        system_ingested_time=now.isoformat(timespec="seconds"),
        freshness_class=fc,
        market_session=session,
        is_current_for_requested_mode=True,
        market_date=market_date,
        maximum_acceptable_age_seconds=sla.get("during_open_session_max_age_seconds", 0),
    )
    return FreshnessValidationResult(True, fc, "freshness contract satisfied", provenance=prov)
