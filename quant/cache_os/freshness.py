"""Freshness evaluation for cache entries (v2.2 §3.4).

FRESH          within TTL — usable for new recommendations
STALE_ALLOWED  past TTL but within the stale-grace window — display only, must
               be labelled; acceptable outside trading hours or when the origin
               source failed
EXPIRED        past the grace window — history/review only, never new advice
DEGRADED       primary source failed, fallback succeeded — must be labelled
UNAVAILABLE    no data at all — scores relying on it must be down-weighted
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from quant.cache_os.policy import ResolvedPolicy


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE_ALLOWED = "stale_allowed"
    EXPIRED = "expired"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


# Statuses whose data may feed a NEW recommendation.
USABLE_FOR_RECOMMENDATION = frozenset({FreshnessStatus.FRESH, FreshnessStatus.DEGRADED})

STATUS_LABEL_ZH = {
    FreshnessStatus.FRESH: "最新",
    FreshnessStatus.STALE_ALLOWED: "稍旧但可用",
    FreshnessStatus.EXPIRED: "已过期",
    FreshnessStatus.DEGRADED: "降级",
    FreshnessStatus.UNAVAILABLE: "不可用",
}


@dataclass(frozen=True)
class FreshnessReport:
    status: FreshnessStatus
    age_seconds: Optional[float]
    ttl_seconds: Optional[float]
    usable_for_recommendation: bool
    label_zh: str
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "age_seconds": round(self.age_seconds, 1) if self.age_seconds is not None else None,
            "ttl_seconds": self.ttl_seconds,
            "usable_for_recommendation": self.usable_for_recommendation,
            "label_zh": self.label_zh,
            "reason": self.reason,
        }


def evaluate_freshness(
    *,
    stored_at: Optional[float],
    policy: ResolvedPolicy,
    degraded: bool = False,
    now: Optional[float] = None,
) -> FreshnessReport:
    """Classify a cache entry. ``stored_at`` is a unix timestamp; None = missing."""
    now = now if now is not None else time.time()
    if stored_at is None:
        return _report(FreshnessStatus.UNAVAILABLE, None, policy, "缓存缺失，数据不可用")

    age = max(0.0, now - float(stored_at))
    ttl = policy.ttl_seconds

    if ttl is None:
        # params-hash-keyed caches (backtests, reports) never expire by time.
        status = FreshnessStatus.DEGRADED if degraded else FreshnessStatus.FRESH
        return _report(status, age, policy, "按参数哈希缓存，参数不变永久有效")

    if age <= ttl:
        status = FreshnessStatus.DEGRADED if degraded else FreshnessStatus.FRESH
        reason = "主源失败，降级数据在 TTL 内" if degraded else "TTL 内"
        return _report(status, age, policy, reason)

    grace = policy.stale_allowed_seconds or ttl
    if age <= grace:
        return _report(FreshnessStatus.STALE_ALLOWED, age, policy,
                       f"超过 TTL {ttl:.0f}s，处于展示宽限期（仅展示，不用于新推荐）")
    return _report(FreshnessStatus.EXPIRED, age, policy, f"超过宽限期，年龄 {age:.0f}s")


def _report(status: FreshnessStatus, age: Optional[float], policy: ResolvedPolicy, reason: str) -> FreshnessReport:
    return FreshnessReport(
        status=status,
        age_seconds=age,
        ttl_seconds=policy.ttl_seconds,
        usable_for_recommendation=status in USABLE_FOR_RECOMMENDATION,
        label_zh=STATUS_LABEL_ZH[status],
        reason=reason,
    )
