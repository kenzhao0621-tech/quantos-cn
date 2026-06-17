#!/usr/bin/env python3
"""End-to-end broker chain test — run today before tomorrow's live session."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8787"
KEY = "demo-local-key-change-in-prod"


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-API-Key": KEY},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    report: dict = {"steps": [], "ok": True}
    steps = [
        ("ecosystem", "GET", "/api/v1/brokers/ecosystem", None),
        ("config_put", "PUT", "/api/v1/brokers/config", {"active_broker": "eastmoney_manual", "readonly": False}),
        ("connect_flow", "POST", "/api/v1/brokers/connect-flow", {
            "broker_id": "eastmoney_manual",
            "open_login": False,
            "sync_watchlist": False,
        }),
        ("launch", "POST", "/api/v1/brokers/launch", {"target": "trade_login"}),
        ("session", "GET", "/api/v1/brokers/session", None),
        ("execution_paths", "GET", "/api/v1/brokers/execution-paths", None),
        ("acceptance", "GET", "/api/v1/brokers/acceptance", None),
    ]
    for name, method, path, body in steps:
        try:
            r = _req(method, path, body)
            ok = r.get("ok", False)
            data = r.get("data") or {}
            detail = {
                "name": name,
                "ok": ok,
                "url": data.get("client_url") or data.get("url") or data.get("login_url"),
                "broker": data.get("broker_id") or data.get("broker_label"),
                "verdict": data.get("verdict"),
            }
            report["steps"].append(detail)
            if not ok and name not in ("acceptance",):
                report["ok"] = False
        except Exception as exc:
            report["steps"].append({"name": name, "ok": False, "error": str(exc)})
            report["ok"] = False

    out = ROOT / "data" / "gateway" / "broker_chain_test.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
