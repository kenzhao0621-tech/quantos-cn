#!/usr/bin/env python3
"""Broker trading sidecar — run on Windows VM (MiniQMT) or Linux (XTP).

Mac Gateway calls this over HTTP for real orders without local xtquant.

Usage (Windows VM with MiniQMT logged in):
  python scripts/broker_sidecar_server.py --host 0.0.0.0 --port 8799 \\
    --miniqmt-path "C:\\国金证券QMT交易端\\userdata_mini" --account YOUR_ACCOUNT

Mac tunnel:
  bash scripts/mac_broker_tunnel.sh user@windows-vm-host
  # Gateway sidecar URL: http://127.0.0.1:8799
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ORDER_LOG = ROOT / "data" / "gateway" / "sidecar_orders.jsonl"

_STATE: dict[str, Any] = {
    "backend": "none",
    "account_id": "",
    "miniqmt_path": "",
    "connected": False,
    "message": "sidecar starting",
    "real_orders": False,
}


def _json_response(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", 0))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def _init_xtquant(miniqmt_path: str, account_id: str) -> dict[str, Any]:
    global _STATE
    try:
        from gateway.brokers.xtquant_bridge import XtQuantBridge, xtquant_available
        avail = xtquant_available(miniqmt_path)
        if not avail.get("runtime_ready"):
            _STATE.update({
                "backend": "xtquant",
                "connected": False,
                "message": avail.get("reason", "xtquant 未就绪"),
                "real_orders": False,
            })
            return {"ok": False, "status": "XTQUANT_NOT_READY", **avail}
        bridge = XtQuantBridge(account_id=account_id, miniqmt_path=avail.get("miniqmt_path", miniqmt_path))
        conn = bridge.connect()
        _STATE.update({
            "backend": "xtquant",
            "account_id": account_id,
            "miniqmt_path": avail.get("miniqmt_path", miniqmt_path),
            "connected": conn.get("ok", False),
            "message": conn.get("message", ""),
            "real_orders": conn.get("ok", False),
            "bridge": bridge,
        })
        return {"ok": conn.get("ok", False), "status": conn.get("status"), **conn}
    except Exception as exc:
        _STATE.update({"backend": "xtquant", "connected": False, "message": str(exc)[:200], "real_orders": False})
        return {"ok": False, "status": "XTQUANT_ERROR", "message": str(exc)[:200]}


def _place_order(body: dict[str, Any]) -> dict[str, Any]:
    symbol = str(body.get("symbol", "")).upper()
    side = str(body.get("side", "BUY")).upper()
    quantity = int(body.get("quantity", 0))
    limit_price = float(body.get("limit_price", 0))
    remark = str(body.get("remark", "QuantOS-sidecar"))
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "limit_price": limit_price,
        "remark": remark,
    }
    bridge = _STATE.get("bridge")
    if bridge and _STATE.get("connected"):
        result = bridge.place_order(symbol=symbol, side=side, quantity=quantity, limit_price=limit_price, remark=remark)
        record["result"] = result
        ORDER_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ORDER_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if result.get("ok"):
            return {
                "ok": True,
                "order_id": result.get("order_id"),
                "message": result.get("message"),
                "backend": "xtquant",
                "legal_boundary": "REAL_BROKER_ORDER",
            }
        return {"ok": False, "error": result.get("error", result)}
    return {
        "ok": False,
        "error": {
            "code": "SIDECAR_NOT_CONNECTED",
            "message": _STATE.get("message") or "Sidecar 未连接 MiniQMT，请先启动客户端并登录",
        },
    }


class SidecarHandler(BaseHTTPRequestHandler):
    api_key = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _auth_ok(self) -> bool:
        if not self.api_key:
            return True
        return self.headers.get("X-Sidecar-Key", "") == self.api_key

    def do_GET(self) -> None:
        if not self._auth_ok():
            _json_response(self, 401, {"ok": False, "error": "unauthorized"})
            return
        path = urlparse(self.path).path
        if path == "/health":
            _json_response(self, 200, {
                "ok": True,
                "platform": platform.system(),
                "backend": _STATE.get("backend"),
                "connected": _STATE.get("connected"),
                "real_orders": _STATE.get("real_orders"),
            })
            return
        if path == "/v1/session":
            _json_response(self, 200, {
                "ok": _STATE.get("connected", False),
                "status": "XTQUANT_CONNECTED" if _STATE.get("connected") else "SIDECAR_IDLE",
                "message": _STATE.get("message"),
                "backend": _STATE.get("backend"),
                "account_id": _STATE.get("account_id"),
                "real_orders": _STATE.get("real_orders"),
                "miniqmt_path": _STATE.get("miniqmt_path"),
            })
            return
        if path == "/v1/positions":
            bridge = _STATE.get("bridge")
            if bridge and _STATE.get("connected"):
                _json_response(self, 200, {"ok": True, "positions": bridge.query_positions()})
                return
            _json_response(self, 200, {"ok": True, "positions": []})
            return
        _json_response(self, 404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if not self._auth_ok():
            _json_response(self, 401, {"ok": False, "error": "unauthorized"})
            return
        path = urlparse(self.path).path
        body = _read_json(self)
        if path == "/v1/order":
            _json_response(self, 200, _place_order(body))
            return
        if path == "/v1/watchlist/sync":
            symbols = body.get("symbols") or []
            bridge = _STATE.get("bridge")
            if bridge and _STATE.get("connected"):
                _json_response(self, 200, bridge.sync_watchlist(symbols))
                return
            _json_response(self, 200, {"ok": True, "mode": "sidecar_deferred", "symbols": symbols})
            return
        _json_response(self, 404, {"ok": False, "error": "not found"})


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantOS broker sidecar")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--miniqmt-path", default=os.environ.get("MINIQMT_PATH", ""))
    parser.add_argument("--account", default=os.environ.get("XTQUANT_ACCOUNT_ID", ""))
    parser.add_argument("--api-key", default=os.environ.get("QUANTOS_BROKER_SIDECAR_KEY", ""))
    args = parser.parse_args()

    SidecarHandler.api_key = args.api_key
    if args.miniqmt_path and args.account:
        init = _init_xtquant(args.miniqmt_path, args.account)
        print(json.dumps(init, ensure_ascii=False, indent=2))
    else:
        _STATE.update({
            "message": "等待 MiniQMT 参数 --miniqmt-path 与 --account；健康检查仍可用",
            "backend": "pending",
        })
        print("Sidecar 启动（未绑定 MiniQMT）— 请传入 --miniqmt-path 与 --account")

    server = ThreadingHTTPServer((args.host, args.port), SidecarHandler)
    print(f"Sidecar listening http://{args.host}:{args.port}  platform={platform.system()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
