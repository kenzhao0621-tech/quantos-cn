"""KronosOS configuration — paths, model selection, runtime limits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SIDECAR_VENV = ROOT / ".venv-kronos"
SIDECAR_PYTHON = SIDECAR_VENV / "bin" / "python"
VENDOR_DIR = ROOT / "vendor" / "kronos"
SIDECAR_SCRIPT = Path(__file__).parent / "sidecar.py"
STATUS_PATH = ROOT / "data" / "quantos" / "kronos_status.json"

DEFAULT_MODEL = "kronos-mini"
MODEL_REPOS = {
    "kronos-mini": ("NeoQuasar/Kronos-mini", "NeoQuasar/Kronos-Tokenizer-2k", 2048),
    "kronos-small": ("NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base", 512),
}
DEFAULT_LOOKBACK = 256
DEFAULT_HORIZON = 5
DEFAULT_N_PATHS = 30
SIDECAR_TIMEOUT_SEC = 180


def sidecar_available() -> tuple[bool, str]:
    """Cheap availability probe — status file + interpreter presence."""
    if not SIDECAR_PYTHON.exists():
        return False, "sidecar_venv_missing"
    if not VENDOR_DIR.exists():
        return False, "kronos_vendor_missing"
    if STATUS_PATH.exists():
        try:
            status: dict[str, Any] = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
            if not status.get("installed"):
                return False, str(status.get("reason") or "kronos_not_installed")
        except Exception:
            return False, "kronos_status_unreadable"
    return True, "ok"
