"""Uvicorn entrypoint for Gateway API — cwd-independent."""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.api.app import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "gateway.api.app:app",
        host="127.0.0.1",
        port=8787,
        app_dir=str(PROJECT_ROOT),
        reload=False,
        log_level="info",
    )
