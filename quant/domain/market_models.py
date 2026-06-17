"""Typed market-data domain models — the stable boundary for the whole app.

These dataclasses are the canonical contract. API routes, the portal BFF, Qlib,
vn.py and reports must consume these and never import private provider functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class DataMode(str, Enum):
    """Where the data is allowed to come from for a given request."""

    LIVE = "LIVE"
    DELAYED = "DELAYED"
    END_OF_DAY = "END_OF_DAY"
    FIXTURE = "FIXTURE"


class Freshness(str, Enum):
    LICENSED_REALTIME = "LICENSED_REALTIME"
    BROKER_REALTIME = "BROKER_REALTIME"
    PROVIDER_REALTIME = "PROVIDER_REALTIME"
    DELAYED_INTRADAY = "DELAYED_INTRADAY"
    END_OF_DAY = "END_OF_DAY"
    STALE = "STALE"
    FIXTURE = "FIXTURE"


class ProviderStatusKind(str, Enum):
    SUCCESS = "SUCCESS"
    SUCCESS_ZERO_RESULTS = "SUCCESS_ZERO_RESULTS"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    AUTH_FAILED = "AUTH_FAILED"
    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    QUALITY_REJECTED = "QUALITY_REJECTED"
    STALE = "STALE"


@dataclass(frozen=True)
class IndexQuote:
    symbol: str
    name: str
    close: float
    change_pct: Optional[float]
    volume: Optional[float]
    amount: Optional[float]
    trade_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "close": self.close,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "amount": self.amount,
            "trade_date": self.trade_date,
        }


@dataclass(frozen=True)
class DatasetCoverage:
    dataset: str
    row_count: int
    last_trade_date: Optional[str]
    last_updated: Optional[str]
    fresh: bool
    blocker: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "row_count": self.row_count,
            "last_trade_date": self.last_trade_date,
            "last_updated": self.last_updated,
            "fresh": self.fresh,
            "blocker": self.blocker,
        }


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    status: ProviderStatusKind
    datasets: list[str] = field(default_factory=list)
    last_ok: Optional[str] = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status.value,
            "datasets": self.datasets,
            "last_ok": self.last_ok,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class MarketOverview:
    """The single rendered contract consumed by the portal market page."""

    mode: DataMode
    freshness: Freshness
    as_of_date: Optional[str]
    indices: list[IndexQuote] = field(default_factory=list)
    advancers: int = 0
    decliners: int = 0
    unchanged: int = 0
    total_symbols: int = 0
    limit_up: int = 0
    limit_down: int = 0
    blocked: bool = False
    blocker_reason: str = ""
    blocker_dataset: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "freshness": self.freshness.value,
            "as_of_date": self.as_of_date,
            "indices": [i.to_dict() for i in self.indices],
            "breadth": {
                "advancers": self.advancers,
                "decliners": self.decliners,
                "unchanged": self.unchanged,
                "total_symbols": self.total_symbols,
                "limit_up": self.limit_up,
                "limit_down": self.limit_down,
            },
            "blocked": self.blocked,
            "blocker_reason": self.blocker_reason,
            "blocker_dataset": self.blocker_dataset,
            "provenance": self.provenance,
        }


@dataclass
class DataRefreshJob:
    job_id: str
    datasets: list[str]
    mode: DataMode
    status: str = "QUEUED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "datasets": self.datasets,
            "mode": self.mode.value,
            "status": self.status,
        }
