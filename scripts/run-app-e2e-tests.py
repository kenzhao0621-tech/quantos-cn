#!/usr/bin/env python3
"""App E2E tests — import paths, server startup, critical API routes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv-china-quant" / "bin" / "python"
REPORT_DIR = ROOT / "docs" / "ai" / "app"
HOST = "127.0.0.1"
PORT = 8787
BASE = f"http://{HOST}:{PORT}"


def _http(path: str, method: str = "GET", headers: dict | None = None, body: bytes | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(f"{BASE}{path}", data=body, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, {"html": True, "length": len(raw)}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw[:200]}


def _wait_health(timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            code, _ = _http("/health")
            if code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _stop_server(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    subprocess.run(["bash", str(ROOT / "scripts/stop-portal.sh")], cwd=str(ROOT), capture_output=True)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    cases: list[dict] = []
    proc: subprocess.Popen | None = None

    # Reset kill switch via API if halted from prior runs
    try:
        risk_h = {"X-API-Key": "dev-service-risk-key", "Content-Type": "application/json"}
        _http("/api/v1/risk/reset-confirm", method="POST", headers=risk_h, body=b"{}")
    except Exception:
        pass

    # 1. Editable install + import from /tmp
    r = subprocess.run([str(PY), "-m", "pip", "install", "-e", str(ROOT)], capture_output=True, text=True)
    cases.append({"case": "editable_install", "passed": r.returncode == 0, "detail": r.stderr[-200:] if r.returncode else "ok"})

    r = subprocess.run([str(PY), "-c", "import gateway; print(gateway.__version__)"], cwd="/tmp", capture_output=True, text=True)
    cases.append({"case": "import_gateway_from_tmp", "passed": r.returncode == 0, "detail": r.stdout.strip()})

    r = subprocess.run([str(PY), "-c", "from gateway.api.app import app"], cwd="/tmp", capture_output=True, text=True)
    cases.append({"case": "import_app_from_tmp", "passed": r.returncode == 0})

    # 2. main.py from /tmp
    r = subprocess.run(
        [str(PY), "-c", "import ast; ast.parse(open(r'" + str(ROOT / "apps/gateway-api/main.py") + "').read()); import gateway.api.app"],
        cwd="/tmp",
        capture_output=True,
        text=True,
    )
    cases.append({"case": "main_py_import", "passed": r.returncode == 0, "detail": r.stderr[-200:] if r.returncode else "ok"})

    # 3. Start server via uvicorn from /tmp cwd
    _stop_server(None)
    proc = subprocess.Popen(
        [str(PY), "-m", "uvicorn", "gateway.api.app:app", "--app-dir", str(ROOT), "--host", HOST, "--port", str(PORT)],
        cwd="/tmp",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    cases.append({"case": "server_start_from_tmp", "passed": _wait_health()})

    from gateway.config import GatewayConfig
    cfg = GatewayConfig.load()
    h = {"X-API-Key": cfg.demo_api_key, "Content-Type": "application/json"}

    for path in ["/health", "/ready", "/portal", "/docs"]:
        code, _ = _http(path)
        cases.append({"case": f"route_{path.replace('/', '_')}", "passed": code == 200})

    code, body = _http("/api/v1/system/status", headers=h)
    cases.append({"case": "system_status", "passed": code == 200 and body.get("ok")})

    code, body = _http("/api/v1/auth/login", method="POST", headers={"Content-Type": "application/json"},
                       body=json.dumps({"role": "admin"}).encode())
    cases.append({"case": "login_admin", "passed": code == 200 and body.get("data", {}).get("role") == "admin"})

    code, body = _http("/api/v1/research/backtest", method="POST", headers=h,
                       body=json.dumps({"as_of_date": "2026-06-16"}).encode())
    cases.append({"case": "backtest", "passed": code == 200 and body.get("data", {}).get("pit_passed") is True})

    code, body = _http("/api/v1/paper/start", method="POST", headers=h, body=b"{}")
    cases.append({"case": "paper_start", "passed": code == 200 and body.get("data", {}).get("status") == "PAPER_TRADING_ACTIVE"})

    code, body = _http("/api/v1/paper/stop", method="POST", headers=h, body=b"{}")
    cases.append({"case": "paper_stop", "passed": code == 200})

    code, body = _http("/api/v1/shadow/start", method="POST", headers=h, body=b"{}")
    cases.append({"case": "shadow_start", "passed": code == 200 and body.get("data", {}).get("zero_real_orders_sent") is True})

    code, body = _http("/api/v1/shadow/stop", method="POST", headers=h, body=b"{}")
    cases.append({"case": "shadow_stop", "passed": code == 200})

    code, body = _http("/api/v1/risk/halt", method="POST", headers=h, body=json.dumps({"reason": "e2e"}).encode())
    cases.append({"case": "risk_halt", "passed": code == 200 and body.get("data", {}).get("halted") is True})

    risk_h = {"X-API-Key": "dev-service-risk-key", "Content-Type": "application/json"}
    code, body = _http("/api/v1/risk/reset-confirm", method="POST", headers=risk_h, body=b"{}")
    cases.append({"case": "risk_reset", "passed": code == 200 and body.get("data", {}).get("reset") is True})

    viewer_h = {"X-API-Key": "svc-portal-read", "Content-Type": "application/json"}
    code, _ = _http("/api/v1/paper/start", method="POST", headers=viewer_h, body=b"{}")
    cases.append({"case": "viewer_paper_denied", "passed": code == 403})

    code, body = _http("/api/v1/system/doctor", method="POST", headers=h, body=b"{}")
    cases.append({"case": "system_doctor", "passed": code == 200 and body.get("data", {}).get("passed") is True})

    # Makefile no duplicate test warning
    r = subprocess.run(["make", "-n", "portal"], cwd=str(ROOT), capture_output=True, text=True)
    cases.append({"case": "make_portal", "passed": r.returncode == 0 and "uvicorn" in r.stdout})

    r = subprocess.run(["make", "-n", "test"], cwd=str(ROOT), capture_output=True, text=True)
    dup_warn = "overriding commands" in r.stderr
    cases.append({"case": "make_no_duplicate_test", "passed": not dup_warn})

    _stop_server(proc)
    proc = None

    passed = all(c["passed"] for c in cases)
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "cases": cases,
        "overall_passed": passed,
        "real_money_disabled": True,
    }
    (REPORT_DIR / "04_API_FUNCTIONAL_ACCEPTANCE.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (REPORT_DIR / "04_API_FUNCTIONAL_ACCEPTANCE.md").write_text(
        f"# API Functional Acceptance\n\n- Overall: **{'PASS' if passed else 'FAIL'}**\n"
        + "\n".join(f"- {c['case']}: {'PASS' if c['passed'] else 'FAIL'}" for c in cases),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
