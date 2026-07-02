"""DataTruth record contract — every datum entering advisory must carry provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class QualityLevel(str, Enum):
    S = "S"           # official exchange / regulator
    A = "A"           # licensed data vendor / major financial media
    B = "B"           # sentiment / auxiliary only
    C = "C"           # unverified
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class DataTruthRecord:
    source_name: str
    source_type: str  # official | exchange | data_vendor | news | derived
    source_url: str
    fetched_at: str
    updated_at: str
    data_version: str
    quality_level: str
    api_name: str = ""
    degraded_reason: str = ""
    is_realtime: bool = False
    is_estimated: bool = False
    field_name: str = ""
    value: Any = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["usable_for_verified_facts"] = self.is_usable_for_verified_facts()
        return d

    def is_usable_for_verified_facts(self) -> bool:
        if not all([self.source_url, self.fetched_at, self.updated_at,
                    self.data_version, self.quality_level]):
            return False
        if self.quality_level in (QualityLevel.DEGRADED.value,
                                  QualityLevel.UNAVAILABLE.value, QualityLevel.C.value):
            return False
        return True

    @classmethod
    def now_fetched(cls, **kwargs: Any) -> "DataTruthRecord":
        ts = datetime.now().isoformat(timespec="seconds")
        return cls(fetched_at=ts, updated_at=kwargs.pop("updated_at", ts), **kwargs)
