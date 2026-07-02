"""Cache metrics — hit/miss/stale/degraded counters per data type (v2.2 §9, §12.1)."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Dict


class CacheMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"hit": 0, "miss": 0, "stale_allowed": 0, "degraded": 0,
                     "unavailable": 0, "force_refresh": 0, "recompute_skipped": 0}
        )

    def record(self, data_type: str, event: str) -> None:
        with self._lock:
            bucket = self._counters[data_type or "unknown"]
            if event not in bucket:
                bucket[event] = 0
            bucket[event] += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            per_type = {k: dict(v) for k, v in self._counters.items()}
        total_hit = sum(v.get("hit", 0) for v in per_type.values())
        total_miss = sum(v.get("miss", 0) for v in per_type.values())
        lookups = total_hit + total_miss
        return {
            "per_data_type": per_type,
            "cache_summary": {
                "hit_rate": round(total_hit / lookups, 4) if lookups else 0.0,
                "hit_count": total_hit,
                "miss_count": total_miss,
                "stale_allowed_count": sum(v.get("stale_allowed", 0) for v in per_type.values()),
                "degraded_count": sum(v.get("degraded", 0) for v in per_type.values()),
                "unavailable_count": sum(v.get("unavailable", 0) for v in per_type.values()),
                "force_refresh_count": sum(v.get("force_refresh", 0) for v in per_type.values()),
                "recompute_skipped_count": sum(v.get("recompute_skipped", 0) for v in per_type.values()),
            },
        }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


_metrics = CacheMetrics()


def get_cache_metrics() -> CacheMetrics:
    return _metrics
