"""Approved secret loading — never log token values."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_LOADED = False


def _load_env_local() -> None:
    global _LOADED
    if _LOADED:
        return
    path = ROOT / ".env.local"
    if not path.exists():
        _LOADED = True
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val
    _LOADED = True


def get(name: str, default: str = "") -> str:
    _load_env_local()
    return os.environ.get(name, default).strip()


def configured(name: str) -> bool:
    return bool(get(name))
