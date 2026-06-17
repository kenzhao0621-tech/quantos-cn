"""Remote broker sidecar client — Mac Gateway connects to Windows/Linux trading agent."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from gateway.brokers.connection_manager import BrokerConfig, load_broker_config


def sidecar_configured(cfg: BrokerConfig | None = None) -> bool:
    cfg = cfg or load_broker_config()
    return bool((cfg.sidecar_url or os.environ.get("QUANTOS_BROKER_SIDECAR_URL", "")).strip())


def _base_url(cfg: BrokerConfig) -> str:
    url = (cfg.sidecar_url or os.environ.get("QUANTOS_BROKER_SIDECAR_URL", "")).strip()
    return url.rstrip("/")


def _api_key(cfg: BrokerConfig) -> str:
    return (cfg.sidecar_api_key or os.environ.get("QUANTOS_BROKER_SIDECAR_KEY", "")).strip()


def sidecar_request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    cfg: BrokerConfig | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    cfg = cfg or load_broker_config()
    base = _base_url(cfg)
    if not base:
        return {"ok": False, "error": {"code": "SIDECAR_NOT_CONFIGURED", "message": "未配置 Sidecar URL"}}
    url = f"{base}{path}"
    data = None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = _api_key(cfg)
    if key:
        headers["X-Sidecar-Key"] = key
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {"ok": True}
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
        except Exception:
            detail = {"message": str(exc)}
        return {"ok": False, "error": detail, "status_code": exc.code}
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "code": "SIDECAR_UNREACHABLE",
                "message": f"无法连接交易 Sidecar ({base}): {exc}",
            },
            "user_action": "请确认 Windows 虚拟机已启动 broker_sidecar_server.py，或运行 scripts/mac_broker_tunnel.sh",
        }


def sidecar_health(cfg: BrokerConfig | None = None) -> dict[str, Any]:
    return sidecar_request("GET", "/health", cfg=cfg)


def sidecar_session(cfg: BrokerConfig | None = None) -> dict[str, Any]:
    return sidecar_request("GET", "/v1/session", cfg=cfg)


def sidecar_place_order(
    *,
    symbol: str,
    side: str,
    quantity: int,
    limit_price: float,
    account_id: str = "",
    remark: str = "",
    cfg: BrokerConfig | None = None,
) -> dict[str, Any]:
    return sidecar_request(
        "POST",
        "/v1/order",
        body={
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "limit_price": limit_price,
            "account_id": account_id,
            "remark": remark,
        },
        cfg=cfg,
        timeout=15.0,
    )


def sidecar_sync_watchlist(symbols: list[str], cfg: BrokerConfig | None = None) -> dict[str, Any]:
    return sidecar_request("POST", "/v1/watchlist/sync", body={"symbols": symbols}, cfg=cfg)


def sidecar_positions(cfg: BrokerConfig | None = None) -> dict[str, Any]:
    return sidecar_request("GET", "/v1/positions", cfg=cfg)


def test_sidecar_connection(cfg: BrokerConfig | None = None) -> dict[str, Any]:
    cfg = cfg or load_broker_config()
    if not sidecar_configured(cfg):
        return {
            "connected": False,
            "status": "SIDECAR_NOT_CONFIGURED",
            "message": "请填写 Sidecar URL（Windows VM 或远程主机地址）",
            "handoff": "remote_sidecar",
            "broker": "mac_sidecar",
            "real_orders": False,
            "mac_note": "Mac 通过 HTTP Sidecar 连接虚拟机内的 MiniQMT/XTP 完成真实下单",
        }
    health = sidecar_health(cfg)
    session = sidecar_session(cfg) if health.get("ok") else {}
    connected = bool(health.get("ok")) and bool(session.get("ok", health.get("ok")))
    return {
        "connected": connected,
        "status": session.get("status") or ("SIDECAR_OK" if health.get("ok") else "SIDECAR_DOWN"),
        "message": session.get("message") or health.get("message") or health.get("error", {}).get("message", ""),
        "handoff": "remote_sidecar",
        "broker": cfg.active_broker if cfg.active_broker == "mac_sidecar" else "mac_sidecar",
        "real_orders": bool(session.get("real_orders")),
        "sidecar_url": _base_url(cfg),
        "backend": session.get("backend") or health.get("backend"),
        "health": health,
        "session": session,
    }
