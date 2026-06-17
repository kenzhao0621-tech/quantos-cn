"""Native engine subprocess bridge — isolated venv invocation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
VNVPY = ROOT / ".venv-vnpy-native" / "bin" / "python"
VQLIB = ROOT / ".venv-qlib-native" / "bin" / "python"


def venv_python(venv: str) -> Path:
    p = ROOT / f".venv-{venv}-native" / "bin" / "python"
    return p


def venv_exists(venv: str) -> bool:
    return venv_python(venv).exists()


def run_native_script(venv: str, script: str, timeout: int = 300) -> dict[str, Any]:
    py = venv_python(venv)
    if not py.exists():
        return {"ok": False, "error": f"{venv} venv missing — run scripts/setup-native-venvs.sh"}
    r = subprocess.run(
        [str(py), str(ROOT / "scripts" / "native" / script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "ok": r.returncode == 0,
        "exit_code": r.returncode,
        "stdout": r.stdout[-3000:],
        "stderr": r.stderr[-1500:],
    }


def native_vnpy_status() -> dict[str, Any]:
    if not venv_exists("vnpy"):
        return {"state": "NOT_INSTALLED", "mode": "SHIM", "venv": str(VNVPY)}
    try:
        r = subprocess.run(
            [str(VNVPY), "-c", "import vnpy; from vnpy.event import EventEngine; from vnpy.trader.engine import MainEngine; print(vnpy.__version__)"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return {"state": "INSTALLED", "mode": "NATIVE", "version": r.stdout.strip(), "venv": str(VNVPY.parent.parent)}
        return {"state": "FAILED", "mode": "SHIM", "error": r.stderr[-500:]}
    except Exception as exc:
        return {"state": "FAILED", "mode": "SHIM", "error": str(exc)}


def native_qlib_status() -> dict[str, Any]:
    if not venv_exists("qlib"):
        return {"state": "NOT_INSTALLED", "mode": "SHIM", "venv": str(VQLIB)}
    try:
        r = subprocess.run(
            [str(VQLIB), "-c", "import qlib; print(qlib.__version__)"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return {"state": "INSTALLED", "mode": "NATIVE", "version": r.stdout.strip(), "venv": str(VQLIB.parent.parent)}
        return {"state": "FAILED", "mode": "SHIM", "error": r.stderr[-500:]}
    except Exception as exc:
        return {"state": "FAILED", "mode": "SHIM", "error": str(exc)}
