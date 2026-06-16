"""Disclosure provider protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable


class DisclosureStatus(str, Enum):
    SUCCESS_WITH_ROWS = "SUCCESS_WITH_ROWS"
    SUCCESS_ZERO_RESULTS = "SUCCESS_ZERO_RESULTS"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
    SOURCE_ACCESS_RESTRICTED = "SOURCE_ACCESS_RESTRICTED"
    RATE_LIMITED = "RATE_LIMITED"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    QUALITY_REJECTED = "QUALITY_REJECTED"


@dataclass
class DisclosureProviderHealth:
    provider_name: str
    configured: bool
    reachable: bool
    status: str
    checked_at: str
    message: str = ""


@dataclass
class DisclosureCapabilities:
    provider_name: str
    exchanges: list[str]
    supports_symbol_filter: bool
    supports_category_filter: bool
    max_page_size: int


@dataclass
class DisclosureFetchResult:
    provider_name: str
    source_class: str
    status: DisclosureStatus
    query_start: str
    query_end: str
    retrieval_time: str
    row_count: int
    rows: list[dict[str, Any]] = field(default_factory=list)
    raw_artifact_paths: list[str] = field(default_factory=list)
    normalized_artifact_path: str = ""
    provider_timestamp: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def query_completed(self) -> bool:
        return self.status in {
            DisclosureStatus.SUCCESS_WITH_ROWS,
            DisclosureStatus.SUCCESS_ZERO_RESULTS,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "source_class": self.source_class,
            "status": self.status.value,
            "query_start": self.query_start,
            "query_end": self.query_end,
            "retrieval_time": self.retrieval_time,
            "row_count": self.row_count,
            "raw_artifact_paths": self.raw_artifact_paths,
            "normalized_artifact_path": self.normalized_artifact_path,
            "provider_timestamp": self.provider_timestamp,
            "warnings": self.warnings,
            "errors": self.errors,
            "query_completed": self.query_completed,
        }


@runtime_checkable
class DisclosureProvider(Protocol):
    name: str

    def health_check(self) -> DisclosureProviderHealth: ...
    def capabilities(self) -> DisclosureCapabilities: ...
    def fetch_announcements(
        self,
        start_time: datetime,
        end_time: datetime,
        symbols: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
    ) -> DisclosureFetchResult: ...
