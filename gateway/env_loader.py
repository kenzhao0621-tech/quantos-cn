"""Load project .env into os.environ before Tushare / provider calls."""

from __future__ import annotations

import os
from pathlib import Path

from gateway.config import ROOT

_LOADED = False


def load_project_env() -> None:
    global _LOADED
    if _LOADED:
        return
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    _LOADED = True


def tushare_configured() -> bool:
    load_project_env()
    return bool(os.environ.get("TUSHARE_TOKEN", "").strip())
