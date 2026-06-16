"""Local disk cache for AKShare responses."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "china-quant"
DEFAULT_TTL_MINUTES = 30


def cache_key(source_id: str, extra: str = "") -> str:
    return hashlib.sha256(f"{source_id}:{extra}".encode()).hexdigest()[:24]


def cache_get(cache_dir: Path, key: str, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> Optional[Any]:
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    cached_at = datetime.fromisoformat(data["_cached_at"])
    if datetime.now() - cached_at > timedelta(minutes=ttl_minutes):
        return None
    return data["payload"]


def cache_set(cache_dir: Path, key: str, payload: Any) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.json"
    path.write_text(
        json.dumps({"_cached_at": datetime.now().isoformat(), "payload": payload}, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
