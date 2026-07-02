"""Source registry loader — config/source_registry.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "config" / "source_registry.yaml"


@lru_cache(maxsize=1)
def load_source_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"sources": {}, "northbound": {}}
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}


def get_source(source_id: str) -> dict[str, Any] | None:
    reg = load_source_registry()
    return (reg.get("sources") or {}).get(source_id)
