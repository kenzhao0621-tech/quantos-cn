"""Unified CacheKey — stable sha256 over a normalized payload (v2.2 §2.3).

Never build cache keys by string concatenation elsewhere; always go through
``build_cache_key`` so key ordering, unicode and nested params are normalized.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

CACHE_SCHEMA_VERSION = "v2.2"

VALID_DATA_TYPES = frozenset({
    "realtime_quote",
    "intraday_bar",
    "ohlcv_daily",
    "adjustment_factor",
    "financial_statement",
    "announcement",
    "policy_news",
    "sector_strength",
    "money_flow",
    "sentiment_news",
    "feature_vector",
    "prediction",
    "agents_research",
    "advisory_result",
    "backtest_result",
    "report_artifact",
})


def _normalize(value: Any) -> Any:
    """Recursively normalize payload values so semantically equal payloads hash equal."""
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def build_cache_key(payload: Dict[str, Any]) -> str:
    """Return stable sha256 cache key from sorted normalized payload."""
    normalized = _normalize(payload)
    blob = json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def params_hash(params: Optional[Dict[str, Any]]) -> str:
    """sha256 over sorted params (v2.2 §4.2). Empty params hash to a stable value."""
    blob = json.dumps(_normalize(params or {}), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CacheKey:
    """Structured cache key per v2.2 §2.3. ``key()`` yields the stable digest."""

    data_type: str
    symbol: str = ""
    market: str = "CN_A_SHARE"
    source: str = ""
    frequency: str = ""
    as_of_date: str = ""
    version: str = CACHE_SCHEMA_VERSION
    params: Dict[str, Any] = field(default_factory=dict)

    def payload(self) -> Dict[str, Any]:
        return {
            "market": self.market,
            "symbol": self.symbol,
            "data_type": self.data_type,
            "source": self.source,
            "frequency": self.frequency,
            "as_of_date": self.as_of_date,
            "version": self.version,
            "params_hash": params_hash(self.params),
        }

    def key(self) -> str:
        return build_cache_key(self.payload())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["cache_key"] = self.key()
        return d
