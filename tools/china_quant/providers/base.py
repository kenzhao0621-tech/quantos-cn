"""Base types for provider-independent data layer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


SCHEMA_VERSION = "2026-06-16-v1"


class DataFreshness(str, Enum):
    REAL_TIME = "REAL_TIME"
    DELAYED = "DELAYED"
    PREVIOUS_CLOSE = "PREVIOUS_CLOSE"
    HISTORICAL = "HISTORICAL"
    FIXTURE = "FIXTURE"
    PARTIAL_DATA = "PARTIAL_DATA"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"


class SourceTrust(str, Enum):
    OFFICIAL_PRIMARY = "OFFICIAL_PRIMARY"
    OFFICIAL_SECONDARY = "OFFICIAL_SECONDARY"
    VERIFIED_DATA_PROVIDER = "VERIFIED_DATA_PROVIDER"
    CREDIBLE_MEDIA = "CREDIBLE_MEDIA"
    UNVERIFIED_MEDIA = "UNVERIFIED_MEDIA"
    SOCIAL_SIGNAL_ONLY = "SOCIAL_SIGNAL_ONLY"


@dataclass
class DataEnvelope:
    provider: str
    payload: Any
    retrieval_timestamp: datetime
    market_timestamp: Optional[datetime]
    timezone: str = "Asia/Shanghai"
    freshness: DataFreshness = DataFreshness.FIXTURE
    schema_version: str = SCHEMA_VERSION
    source_id: str = ""
    license_note: str = "research only; no redistribution"
    limitations: list[str] = field(default_factory=list)
    trust: SourceTrust = SourceTrust.VERIFIED_DATA_PROVIDER
    data_hash: str = ""

    def __post_init__(self) -> None:
        if not self.data_hash and self.payload is not None:
            raw = json.dumps(self.payload, sort_keys=True, default=str)
            self.data_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]


class ProviderError(Exception):
    def __init__(self, message: str, *, provider: str = "", retryable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


class BaseProvider:
    name: str = "base"

    def health(self) -> bool:
        return True
