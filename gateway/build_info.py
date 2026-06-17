"""Build/version metadata for runtime forensics and portal cache busting."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PORTAL_DIR = ROOT / "apps" / "portal-web"
_STARTED_AT = datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def git_commit(full: bool = False) -> str:
    try:
        if full:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL
            ).strip()
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def git_dirty() -> bool:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL
        )
        return bool(out.strip())
    except Exception:
        return False


def frontend_build_id() -> str:
    parts: list[str] = [git_commit()]
    for name in ("index.html", "app.js", "viewmodels.js", "ui-render.js", "quantos.js", "styles.css"):
        p = PORTAL_DIR / name
        if p.exists():
            parts.append(f"{name}:{int(p.stat().st_mtime)}")
    return "-".join(parts)[:64]


@lru_cache(maxsize=1)
def portal_build_id() -> str:
    """Stable build id captured once per running process.

    Both the rendered portal HTML and the /version endpoint use THIS value, so
    they always agree within a single server. A mismatch therefore only occurs
    when the browser is holding HTML from a previous server instance — exactly
    the case where a hard refresh actually helps.
    """
    return frontend_build_id()


def backend_build_id() -> str:
    return f"gateway-{git_commit()}-{int((ROOT / 'gateway' / 'api' / 'app.py').stat().st_mtime)}"


def version_payload() -> dict[str, Any]:
    import importlib
    import inspect
    import gateway

    app_module = importlib.import_module("gateway.api.app")

    return {
        "git_commit": git_commit(full=True),
        "git_commit_short": git_commit(),
        "git_dirty": git_dirty(),
        "backend_build_id": backend_build_id(),
        "frontend_build_id": frontend_build_id(),
        "portal_build_id": portal_build_id(),
        "gateway_module_path": inspect.getfile(gateway),
        "app_module_path": inspect.getfile(app_module),
        "repository_root": str(ROOT),
        "started_at": _STARTED_AT,
        "process_id": os.getpid(),
        "real_money_execution_disabled": True,
    }
