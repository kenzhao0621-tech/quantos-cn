"""Provider attempt results — V4 frozen contract."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional


class ProviderStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    EMPTY = "EMPTY"
    TIMEOUT = "TIMEOUT"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class ProviderResult:
    """Immutable result for a single provider attempt on one dataset."""

    provider: str
    dataset: str
    status: ProviderStatus
    payload: Any = None
    error: Optional[str] = None
    attempt: int = 0
    elapsed_ms: float = 0.0
    retrieved_at: str = ""
    data_hash: str = ""
    row_count: int = 0
    freshness: str = ""
    limitations: tuple[str, ...] = ()
    endpoint: str = ""
    source_dataset: str = ""
    run_id: str = ""
    market_date: str = ""
    is_live: bool = False
    is_end_of_day: bool = False
    is_manual: bool = False
    is_fixture: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)

    @property
    def ok(self) -> bool:
        return self.status == ProviderStatus.SUCCESS
