"""CacheRegistry — the CacheOS facade (L0 memory → L1 disk → loader).

Usage:

    registry = get_cache_registry()
    result = registry.get_or_compute(
        CacheKey(data_type="advisory_result", symbol="600519.SH", as_of_date="2026-07-01"),
        loader=compute_fn,          # only called on miss / force refresh
        persist=True,               # also write to L1 disk
    )
    result.value, result.freshness, result.cache_status

The loader must return either the raw value or a (value, meta_dict) tuple where
meta may carry source/source_url/updated_at/degraded. On loader failure the
registry falls back to a STALE_ALLOWED entry when one exists (honestly
labelled) instead of fabricating data.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from quant.cache_os.cache_key import CacheKey
from quant.cache_os.freshness import FreshnessReport, FreshnessStatus, evaluate_freshness
from quant.cache_os.metrics import get_cache_metrics
from quant.cache_os.policy import CachePolicyRegistry, get_policy_registry
from quant.cache_os.storage import CacheEntry, DiskStore, MemoryStore, make_entry

logger = logging.getLogger(__name__)


@dataclass
class CacheResult:
    value: Any
    cache_status: str  # hit / miss / stale_allowed / force_refresh / unavailable
    freshness: FreshnessReport
    key: str
    data_type: str
    source: str = ""
    source_url: str = ""
    updated_at: str = ""
    stored_at: Optional[float] = None
    elapsed_ms: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def explain(self) -> Dict[str, Any]:
        """Cache provenance block for the explanation layer."""
        return {
            "cache_status": self.cache_status,
            "cache_key": self.key,
            "data_type": self.data_type,
            "freshness": self.freshness.to_dict(),
            "source": self.source,
            "source_url": self.source_url,
            "updated_at": self.updated_at,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


class CacheRegistry:
    def __init__(
        self,
        *,
        policy_registry: Optional[CachePolicyRegistry] = None,
        disk_dir: Optional[Path] = None,
    ) -> None:
        self.policies = policy_registry or get_policy_registry()
        self.memory = MemoryStore()
        self.disk = DiskStore(disk_dir)
        self.metrics = get_cache_metrics()

    # ------------------------------------------------------------------
    def get_or_compute(
        self,
        cache_key: CacheKey,
        loader: Callable[[], Any],
        *,
        persist: bool = False,
        force_refresh: bool = False,
        allow_stale_on_failure: bool = True,
    ) -> CacheResult:
        key = cache_key.key()
        data_type = cache_key.data_type
        policy = self.policies.resolve(data_type)
        started = time.perf_counter()

        entry: Optional[CacheEntry] = None
        if not force_refresh:
            entry = self.memory.get(key)
            if entry is None and persist:
                entry = self.disk.get(key, data_type)
                if entry is not None:
                    self.memory.put(entry)
            if entry is not None:
                report = evaluate_freshness(stored_at=entry.stored_at, policy=policy, degraded=entry.degraded)
                if report.status in (FreshnessStatus.FRESH, FreshnessStatus.DEGRADED):
                    self.metrics.record(data_type, "hit")
                    if report.status is FreshnessStatus.DEGRADED:
                        self.metrics.record(data_type, "degraded")
                    return self._result(entry, "hit", report, started)
        else:
            self.metrics.record(data_type, "force_refresh")

        # Miss (or forced): run the loader.
        try:
            raw = loader()
        except Exception as exc:
            logger.warning("cache loader failed for %s (%s): %s", data_type, key[:12], exc)
            if allow_stale_on_failure:
                stale = entry or self.memory.get(key) or (self.disk.get(key, data_type) if persist else None)
                if stale is not None:
                    report = evaluate_freshness(stored_at=stale.stored_at, policy=policy, degraded=True)
                    if report.status is not FreshnessStatus.EXPIRED:
                        self.metrics.record(data_type, "stale_allowed")
                        return self._result(stale, "stale_allowed", report, started,
                                            extra_meta={"loader_error": str(exc)[:200]})
            self.metrics.record(data_type, "unavailable")
            report = evaluate_freshness(stored_at=None, policy=policy)
            return CacheResult(
                value=None, cache_status="unavailable", freshness=report, key=key,
                data_type=data_type, elapsed_ms=(time.perf_counter() - started) * 1000,
                meta={"loader_error": str(exc)[:200]},
            )

        value, meta = _split_loader_output(raw)
        new_entry = make_entry(
            key, value,
            data_type=data_type,
            source=str(meta.get("source", "")),
            source_url=str(meta.get("source_url", "")),
            updated_at=str(meta.get("updated_at", "")),
            degraded=bool(meta.get("degraded")),
            meta={k: v for k, v in meta.items()
                  if k not in ("source", "source_url", "updated_at", "degraded")},
        )
        self.memory.put(new_entry)
        if persist:
            try:
                self.disk.put(new_entry)
            except Exception as exc:  # disk persistence is best-effort
                logger.warning("disk cache write failed for %s: %s", key[:12], exc)
        self.metrics.record(data_type, "miss")
        if new_entry.degraded:
            self.metrics.record(data_type, "degraded")
        report = evaluate_freshness(stored_at=new_entry.stored_at, policy=policy, degraded=new_entry.degraded)
        status = "force_refresh" if force_refresh else "miss"
        return self._result(new_entry, status, report, started)

    # ------------------------------------------------------------------
    def peek(self, cache_key: CacheKey, *, persist: bool = False) -> Optional[CacheResult]:
        """Inspect the cache without computing anything."""
        key = cache_key.key()
        policy = self.policies.resolve(cache_key.data_type)
        entry = self.memory.get(key) or (self.disk.get(key, cache_key.data_type) if persist else None)
        if entry is None:
            return None
        report = evaluate_freshness(stored_at=entry.stored_at, policy=policy, degraded=entry.degraded)
        return self._result(entry, "peek", report, time.perf_counter())

    def invalidate(self, cache_key: CacheKey, *, persist: bool = False) -> bool:
        key = cache_key.key()
        removed = self.memory.delete(key)
        if persist:
            removed = self.disk.delete(key, cache_key.data_type) or removed
        return removed

    def _result(
        self,
        entry: CacheEntry,
        status: str,
        report: FreshnessReport,
        started: float,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> CacheResult:
        meta = dict(entry.meta)
        if extra_meta:
            meta.update(extra_meta)
        return CacheResult(
            value=entry.value,
            cache_status=status,
            freshness=report,
            key=entry.key,
            data_type=entry.data_type,
            source=entry.source,
            source_url=entry.source_url,
            updated_at=entry.updated_at,
            stored_at=entry.stored_at,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            meta=meta,
        )


def _split_loader_output(raw: Any) -> Tuple[Any, Dict[str, Any]]:
    if isinstance(raw, tuple) and len(raw) == 2 and isinstance(raw[1], dict):
        return raw[0], raw[1]
    return raw, {}


_registry: Optional[CacheRegistry] = None


def get_cache_registry() -> CacheRegistry:
    global _registry
    if _registry is None:
        _registry = CacheRegistry()
    return _registry
