"""Data freshness gate — reject stale data for live decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class DataStatus(str, Enum):
    REAL_TIME = "REAL_TIME"
    DELAYED = "DELAYED"
    PREVIOUS_CLOSE = "PREVIOUS_CLOSE"
    PARTIAL_DATA = "PARTIAL_DATA"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


@dataclass
class FreshnessResult:
    status: DataStatus
    live_decision_ok: bool
    message: str
    data_timestamp: Optional[datetime]
    checked_at: datetime


def assess_freshness(
    data_timestamp: Optional[datetime],
    *,
    max_age_minutes_live: int = 15,
    max_age_minutes_delayed: int = 120,
    now: Optional[datetime] = None,
) -> FreshnessResult:
    now = now or datetime.now()
    if data_timestamp is None:
        return FreshnessResult(
            DataStatus.DATA_UNAVAILABLE,
            False,
            "Data is not current enough for a live entry decision.",
            None,
            now,
        )
    age = now - data_timestamp
    if age <= timedelta(minutes=max_age_minutes_live):
        return FreshnessResult(
            DataStatus.REAL_TIME,
            True,
            "数据可用于盘中决策参考（仍需结合规则与风险）。",
            data_timestamp,
            now,
        )
    if age <= timedelta(minutes=max_age_minutes_delayed):
        return FreshnessResult(
            DataStatus.DELAYED,
            False,
            "Data is not current enough for a live entry decision.",
            data_timestamp,
            now,
        )
    if age <= timedelta(hours=24):
        return FreshnessResult(
            DataStatus.PREVIOUS_CLOSE,
            False,
            "Data is not current enough for a live entry decision.",
            data_timestamp,
            now,
        )
    return FreshnessResult(
        DataStatus.DATA_UNAVAILABLE,
        False,
        "Data is not current enough for a live entry decision.",
        data_timestamp,
        now,
    )
