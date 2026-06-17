"""Broker connection profiles — config persistence and connectivity checks.

Supports official handoff paths (Eastmoney manual, QMT order file drop, XTP TCP probe).
Does not store passwords; real orders still require user confirmation on broker platforms.
"""

from __future__ import annotations

import json
import socket
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT

from gateway.brokers.cn_broker_registry import list_broker_profiles

CONFIG_PATH = ROOT / "data" / "gateway" / "broker_config.json"

BROKER_PROFILES: dict[str, dict[str, Any]] = list_broker_profiles()


@dataclass
class BrokerConfig:
    active_broker: str = "eastmoney_manual"
    account_id: str = ""
    qmt_order_dir: str = ""
    xtp_host: str = ""
    xtp_port: int = 6002
    sidecar_url: str = ""
    sidecar_api_key: str = ""
    auto_trade_via_sidecar: bool = False
    readonly: bool = True
    last_test_at: str = ""
    last_test_status: str = "NOT_TESTED"
    last_test_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_broker_config() -> BrokerConfig:
    if not CONFIG_PATH.exists():
        return BrokerConfig()
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    defaults = BrokerConfig().to_dict()
    defaults.update({k: v for k, v in raw.items() if k in defaults})
    return BrokerConfig(
        active_broker=str(defaults.get("active_broker") or "eastmoney_manual"),
        account_id=str(defaults.get("account_id") or ""),
        qmt_order_dir=str(defaults.get("qmt_order_dir") or ""),
        xtp_host=str(defaults.get("xtp_host") or ""),
        xtp_port=int(defaults.get("xtp_port") or 6002),
        sidecar_url=str(defaults.get("sidecar_url") or ""),
        sidecar_api_key=str(defaults.get("sidecar_api_key") or ""),
        auto_trade_via_sidecar=bool(defaults.get("auto_trade_via_sidecar", False)),
        readonly=bool(defaults.get("readonly", True)),
        last_test_at=str(defaults.get("last_test_at") or ""),
        last_test_status=str(defaults.get("last_test_status") or "NOT_TESTED"),
        last_test_message=str(defaults.get("last_test_message") or ""),
    )


def save_broker_config(data: dict[str, Any]) -> BrokerConfig:
    current = load_broker_config().to_dict()
    current.update({k: v for k, v in data.items() if k in current and k not in ("last_test_at", "last_test_status", "last_test_message")})
    cfg = BrokerConfig(**{k: current[k] for k in BrokerConfig.__dataclass_fields__})  # type: ignore[arg-type]
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def test_broker_connection(cfg: BrokerConfig | None = None) -> dict[str, Any]:
    cfg = cfg or load_broker_config()
    profile = BROKER_PROFILES.get(cfg.active_broker, BROKER_PROFILES["paper_only"])
    now = datetime.now(timezone.utc).isoformat()

    if cfg.active_broker == "mac_sidecar" or (cfg.auto_trade_via_sidecar and cfg.sidecar_url):
        from gateway.brokers.remote_sidecar import test_sidecar_connection
        result = test_sidecar_connection(cfg)
        result["broker"] = cfg.active_broker
    elif cfg.active_broker == "qmt_local":
        from gateway.brokers.xtquant_bridge import xtquant_available, get_xtquant_bridge
        xt = xtquant_available(cfg.qmt_order_dir or "")
        if xt.get("runtime_ready") and cfg.account_id:
            bridge = get_xtquant_bridge(account_id=cfg.account_id, miniqmt_path=xt.get("miniqmt_path", ""))
            conn = bridge.connect()
            result = {
                "connected": conn.get("ok", False),
                "status": conn.get("status", "XTQUANT_FAILED"),
                "message": conn.get("message", conn.get("reason", "")),
                "handoff": "xtquant_api",
                "broker": cfg.active_broker,
                "real_orders": conn.get("ok", False),
                "miniqmt_path": xt.get("miniqmt_path"),
                "package_installed": True,
            }
        elif xt.get("package_stub_only") or (xt.get("package_installed") and not xt.get("runtime_ready")):
            result = {
                "connected": False,
                "status": "XTQUANT_CLIENT_REQUIRED",
                "message": xt.get("reason", "需 Windows MiniQMT 完整客户端"),
                "handoff": "xtquant_api",
                "broker": cfg.active_broker,
                "real_orders": False,
                "package_stub_only": xt.get("package_stub_only", False),
                "runtime_ready": False,
                "platform_note": xt.get("platform_note"),
            }
        elif xt.get("runtime_ready") and not cfg.account_id:
            result = {
                "connected": False,
                "status": "ACCOUNT_REQUIRED",
                "message": "xttrader 就绪，请填写资金账号并确保 MiniQMT 已登录",
                "handoff": "xtquant_api",
                "broker": cfg.active_broker,
                "real_orders": False,
                "runtime_ready": True,
            }
        else:
            p = Path(cfg.qmt_order_dir).expanduser()
            if p.exists() and p.is_dir() and os_access_writable(p):
                msg = f"CSV 目录可写: {p}"
                if not xt.get("available"):
                    msg += " · xtquant 未就绪，请配置 MINIQMT_PATH 并启动 MiniQMT"
                result = {"connected": True, "status": "QMT_CSV_READY", "message": msg, "handoff": "qmt_csv_drop", "broker": cfg.active_broker, "real_orders": False}
            else:
                result = {"connected": False, "status": "PATH_INVALID", "message": f"QMT 目录不存在或不可写: {p}", "handoff": "qmt_csv_drop", "broker": cfg.active_broker}
    elif cfg.active_broker == "xtp_readonly":
        ok, msg = _tcp_probe(cfg.xtp_host, int(cfg.xtp_port), timeout=2.5)
        result = {
            "connected": ok,
            "status": "XTP_REACHABLE" if ok else "XTP_UNREACHABLE",
            "message": msg,
            "handoff": "xtp_api",
            "broker": cfg.active_broker,
        }
    elif _is_browser_broker(cfg.active_broker):
        from gateway.brokers.broker_launcher import build_broker_urls
        from gateway.brokers.cn_broker_registry import CN_BROKER_ECOSYSTEM

        spec = CN_BROKER_ECOSYSTEM.get(cfg.active_broker, {})
        acct = cfg.account_id or "（未填写资金账号）"
        urls = build_broker_urls(cfg.active_broker)
        result = {
            "connected": True,
            "status": "BROKER_WEB_READY",
            "message": f"{spec.get('label', cfg.active_broker)} 官方入口可跳转 · 账号 {acct}",
            "handoff": "broker_browser",
            "broker": cfg.active_broker,
            "portal_url": urls.get("trade_login") or urls.get("portal"),
            "quote_portal": urls.get("portal"),
            "real_orders": False,
            "auto_launch": True,
            "ecosystem": spec.get("ecosystem", []),
        }
    else:
        result = {"connected": True, "status": "SIMULATION_READY", "message": "Paper/Shadow 模拟路径可用", "handoff": "simulation", "broker": cfg.active_broker}

    cfg.last_test_at = now
    cfg.last_test_status = result["status"]
    cfg.last_test_message = result["message"]
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    result["config"] = cfg.to_dict()
    result["profile"] = profile
    return result


def _is_browser_broker(broker_id: str) -> bool:
    from gateway.brokers.broker_launcher import is_browser_broker
    return is_browser_broker(broker_id)


def os_access_writable(path: Path) -> bool:
    try:
        test = path / ".quantos_write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _tcp_probe(host: str, port: int, *, timeout: float) -> tuple[bool, str]:
    if not host:
        return False, "XTP host 未配置"
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP {host}:{port} 可达（只读权限仍需券商开通）"
    except OSError as exc:
        return False, f"无法连接 {host}:{port}: {exc}"
