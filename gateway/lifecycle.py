"""Gateway process lifecycle — PID lock, readiness, graceful shutdown."""

from __future__ import annotations

import atexit
import os
import signal
import socket
from pathlib import Path
from typing import Any

from gateway.config import ROOT

PID_PATH = ROOT / "data" / "gateway" / "gateway.pid"
PORT = int(os.environ.get("GATEWAY_PORT", "8787"))


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def port_in_use(port: int = PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def acquire_pid_lock() -> dict[str, Any]:
    """Ensure single gateway instance; clean stale PID."""
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PID_PATH.exists():
        try:
            old = int(PID_PATH.read_text(encoding="utf-8").strip())
            if _is_alive(old):
                return {"ok": False, "reason": "ALREADY_RUNNING", "pid": old, "port": PORT}
            PID_PATH.unlink(missing_ok=True)
        except ValueError:
            PID_PATH.unlink(missing_ok=True)
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")

    def _cleanup() -> None:
        try:
            if PID_PATH.exists() and int(PID_PATH.read_text()) == os.getpid():
                PID_PATH.unlink(missing_ok=True)
        except Exception:
            pass

    atexit.register(_cleanup)
    return {"ok": True, "pid": os.getpid(), "port": PORT}


def release_pid_lock() -> None:
    PID_PATH.unlink(missing_ok=True)


def readiness_payload(*, mode: str, data_gate_ok: bool = True) -> dict[str, Any]:
    from gateway.build_info import version_payload

    return {
        "status": "ready" if data_gate_ok else "degraded",
        "mode": mode,
        "pid": os.getpid(),
        **version_payload(),
    }
