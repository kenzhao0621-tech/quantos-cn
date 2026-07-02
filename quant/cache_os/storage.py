"""Cache storage backends: L0 in-process memory and L1 local JSON disk.

Both store the payload together with metadata (stored_at, source, updated_at,
degraded flag) so freshness and provenance can always be reconstructed.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DISK_DIR = ROOT / "data" / "cache_os"


@dataclass
class CacheEntry:
    key: str
    value: Any
    stored_at: float
    data_type: str = ""
    source: str = ""
    source_url: str = ""
    updated_at: str = ""
    degraded: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "stored_at": self.stored_at,
            "data_type": self.data_type,
            "source": self.source,
            "source_url": self.source_url,
            "updated_at": self.updated_at,
            "degraded": self.degraded,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CacheEntry":
        return cls(
            key=d.get("key", ""),
            value=d.get("value"),
            stored_at=float(d.get("stored_at") or 0.0),
            data_type=d.get("data_type", ""),
            source=d.get("source", ""),
            source_url=d.get("source_url", ""),
            updated_at=d.get("updated_at", ""),
            degraded=bool(d.get("degraded")),
            meta=dict(d.get("meta") or {}),
        )


class MemoryStore:
    """L0 — process-local, thread-safe, bounded."""

    def __init__(self, max_entries: int = 2048) -> None:
        self._lock = threading.Lock()
        self._data: Dict[str, CacheEntry] = {}
        self.max_entries = max_entries

    def get(self, key: str) -> Optional[CacheEntry]:
        with self._lock:
            return self._data.get(key)

    def put(self, entry: CacheEntry) -> None:
        with self._lock:
            if len(self._data) >= self.max_entries and entry.key not in self._data:
                oldest = min(self._data.values(), key=lambda e: e.stored_at)
                self._data.pop(oldest.key, None)
            self._data[entry.key] = entry

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._data.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._data)


class DiskStore:
    """L1 — one JSON file per entry under data/cache_os/<data_type>/<key>.json.

    JSON-serialisable payloads only; larger artifacts (parquet etc.) should keep
    their existing storage and register a pointer here.
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_DISK_DIR
        self._lock = threading.Lock()

    def _path(self, key: str, data_type: str) -> Path:
        sub = data_type or "misc"
        return self.base_dir / sub / f"{key}.json"

    def get(self, key: str, data_type: str = "") -> Optional[CacheEntry]:
        path = self._path(key, data_type)
        if not path.exists():
            return None
        try:
            return CacheEntry.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None

    def put(self, entry: CacheEntry) -> None:
        path = self._path(entry.key, entry.data_type)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(entry.to_dict(), ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            tmp.replace(path)

    def delete(self, key: str, data_type: str = "") -> bool:
        path = self._path(key, data_type)
        if path.exists():
            path.unlink()
            return True
        return False


def make_entry(
    key: str,
    value: Any,
    *,
    data_type: str,
    source: str = "",
    source_url: str = "",
    updated_at: str = "",
    degraded: bool = False,
    meta: Optional[Dict[str, Any]] = None,
) -> CacheEntry:
    return CacheEntry(
        key=key,
        value=value,
        stored_at=time.time(),
        data_type=data_type,
        source=source,
        source_url=source_url,
        updated_at=updated_at,
        degraded=degraded,
        meta=dict(meta or {}),
    )
