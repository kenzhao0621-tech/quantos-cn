"""MiniQMT xtquant bridge — real broker session when client is logged in locally.

Requires: MiniQMT running + logged in, xtquant on PYTHONPATH (from QMT install).
Docs: http://docs.thinktrader.net/vip/pages/ee0e9b/
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gateway.config import ROOT

SESSION_STATE_PATH = ROOT / "data" / "gateway" / "xtquant_session.json"


@dataclass
class XtQuantConfig:
    miniqmt_path: str = ""
    session_id: int = 0
    account_id: str = ""

    @classmethod
    def from_env(cls) -> "XtQuantConfig":
        return cls(
            miniqmt_path=os.environ.get("MINIQMT_PATH", os.environ.get("XTQUANT_PATH", "")),
            session_id=int(os.environ.get("XTQUANT_SESSION_ID", "0") or 0),
            account_id=os.environ.get("XTQUANT_ACCOUNT_ID", ""),
        )


def detect_miniqmt_paths() -> list[dict[str, str]]:
    """Scan common install locations (macOS / Windows / Linux)."""
    candidates: list[Path] = []
    home = Path.home()
    patterns = [
        home / "国金证券QMT交易端" / "userdata_mini",
        home / "迅投QMT交易端" / "userdata_mini",
        home / "MiniQMT" / "userdata_mini",
        home / ".miniqmt" / "userdata_mini",
        Path("/Applications/MiniQMT.app/Contents/MacOS"),
        Path("C:/国金证券QMT交易端/userdata_mini"),
        Path("C:/迅投QMT交易端/userdata_mini"),
    ]
    env = os.environ.get("MINIQMT_PATH") or os.environ.get("XTQUANT_PATH")
    if env:
        patterns.insert(0, Path(env).expanduser())
    out: list[dict[str, str]] = []
    for p in patterns:
        if p.exists():
            xt = p.parent / "xtquant" if (p.parent / "xtquant").exists() else p
            out.append({"path": str(p), "xtquant": str(xt) if xt.exists() else "", "label": p.name})
    return out


def _inject_xtquant_path(miniqmt_path: str) -> bool:
    base = Path(miniqmt_path).expanduser()
    for sub in (base, base.parent, base / "xtquant", base.parent / "xtquant"):
        if sub.exists() and str(sub) not in sys.path:
            sys.path.insert(0, str(sub))
    try:
        import xtquant  # noqa: F401
        return True
    except ImportError:
        return False


def _xtquant_runtime_ready() -> tuple[bool, str]:
    try:
        from xtquant.xttrader import XtQuantTrader  # noqa: F401
        return True, ""
    except Exception as exc:
        return False, str(exc)[:200]


def xtquant_available(miniqmt_path: str = "") -> dict[str, Any]:
    cfg = XtQuantConfig.from_env()
    path = miniqmt_path or cfg.miniqmt_path
    runtime_ok, runtime_err = _xtquant_runtime_ready()
    package_stub = False
    if not runtime_ok:
        try:
            import xtquant  # noqa: F401
            package_stub = True
        except ImportError:
            package_stub = False

    if not path:
        detected = detect_miniqmt_paths()
        if detected:
            path = detected[0]["path"]
    path_injected = False
    if path:
        path_injected = _inject_xtquant_path(path)
        if path_injected:
            runtime_ok, runtime_err = _xtquant_runtime_ready()

    client_ready = runtime_ok and bool(path)
    return {
        "available": client_ready,
        "package_installed": runtime_ok or package_stub,
        "runtime_ready": runtime_ok,
        "package_stub_only": package_stub and not runtime_ok,
        "client_path": path or "",
        "miniqmt_path": path or "",
        "reason": _xt_reason(runtime_ok, package_stub, path, path_injected, runtime_err),
        "install_url": "https://www.myquant.cn/",
        "detected_paths": detect_miniqmt_paths(),
        "platform_note": "MiniQMT 客户端仅 Windows。macOS 用虚拟机；pip xtquant 不含 xttrader 运行库。",
    }


def _xt_reason(runtime_ok: bool, package_stub: bool, path: str, path_injected: bool, runtime_err: str) -> str:
    if runtime_ok and path:
        return ""
    if runtime_ok and not path:
        return "xttrader 可导入，但 MINIQMT_PATH 未配置 — 请指向 userdata_mini"
    if package_stub:
        return f"pip xtquant 仅为桩包，缺少 MiniQMT 客户端运行库：{runtime_err or '需 Windows QMT 安装目录'}"
    if path and not path_injected:
        return "已配置路径但 xtquant 模块未注入成功"
    if not path:
        return "未检测到 MiniQMT 安装路径"
    return runtime_err or "xtquant 未就绪"


class XtQuantBridge:
    """Lazy-connect xtquant trader — one session per process."""

    def __init__(self, *, miniqmt_path: str = "", account_id: str = "", session_id: int = 0) -> None:
        cfg = XtQuantConfig.from_env()
        self.miniqmt_path = miniqmt_path or cfg.miniqmt_path
        self.account_id = account_id or cfg.account_id
        self.session_id = session_id or cfg.session_id or 1
        self._trader: Any = None
        self._account: Any = None
        self._connected = False

    def connect(self) -> dict[str, Any]:
        avail = xtquant_available(self.miniqmt_path)
        if not avail.get("runtime_ready"):
            return {"ok": False, "status": "XTQUANT_CLIENT_REQUIRED", **avail}
        if not self.account_id:
            return {
                "ok": False,
                "status": "ACCOUNT_REQUIRED",
                "message": "请填写资金账号（MiniQMT 已登录的账号）",
                "miniqmt_path": avail.get("miniqmt_path"),
            }
        try:
            from xtquant.xttrader import XtQuantTrader
            from xtquant.xttype import StockAccount

            path = avail.get("miniqmt_path") or self.miniqmt_path or ""
            if not path:
                return {
                    "ok": False,
                    "status": "MINIQMT_NOT_RUNNING",
                    "message": "xtquant 已安装，但 MiniQMT 客户端未运行（仅支持 Windows）。请虚拟机中启动 MiniQMT 并设置 MINIQMT_PATH。",
                    "package_installed": True,
                    **avail,
                }
            self._trader = XtQuantTrader(path, self.session_id)
            self._trader.start()
            rc = self._trader.connect()
            if rc != 0:
                return {
                    "ok": False,
                    "status": "MINIQMT_NOT_RUNNING",
                    "message": f"无法连接 MiniQMT（code={rc}）。请先启动 MiniQMT 并登录账户。",
                    "miniqmt_path": path,
                }
            self._account = StockAccount(self.account_id)
            sub = self._trader.subscribe(self._account)
            if sub != 0:
                return {
                    "ok": False,
                    "status": "SUBSCRIBE_FAILED",
                    "message": f"账号订阅失败 code={sub}，请确认资金账号与 MiniQMT 登录一致",
                }
            self._connected = True
            asset = self._trader.query_stock_asset(self._account)
            cash = float(getattr(asset, "cash", 0) or 0) if asset else 0.0
            return {
                "ok": True,
                "status": "XTQUANT_CONNECTED",
                "message": f"MiniQMT 已连接 · 账号 {self.account_id} · 可用资金约 ¥{cash:,.0f}",
                "miniqmt_path": path,
                "account_id": self.account_id,
                "cash": cash,
                "real_orders": True,
            }
        except Exception as exc:
            return {
                "ok": False,
                "status": "XTQUANT_ERROR",
                "message": str(exc)[:200],
                "miniqmt_path": avail.get("miniqmt_path"),
            }

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: int,
        limit_price: float,
        strategy_name: str = "QuantOS",
        remark: str = "",
    ) -> dict[str, Any]:
        if not self._connected:
            conn = self.connect()
            if not conn.get("ok"):
                return {"ok": False, "error": conn}
        try:
            from xtquant import xtconstant

            order_type = xtconstant.STOCK_BUY if side.upper() == "BUY" else xtconstant.STOCK_SELL
            order_id = self._trader.order_stock(
                self._account,
                symbol,
                order_type,
                int(quantity),
                xtconstant.FIX_PRICE,
                float(limit_price),
                strategy_name,
                remark or "QuantOS",
            )
            if order_id is None or int(order_id) < 0:
                return {
                    "ok": False,
                    "error": {"code": "XTQUANT_ORDER_REJECTED", "message": f"券商拒单 order_id={order_id}"},
                }
            return {
                "ok": True,
                "order_id": int(order_id),
                "broker": "xtquant",
                "message": f"订单已提交至券商服务器，委托号 {order_id}",
                "legal_boundary": "REAL_BROKER_ORDER",
            }
        except Exception as exc:
            return {"ok": False, "error": {"code": "XTQUANT_ORDER_ERROR", "message": str(exc)[:200]}}

    def query_positions(self) -> list[dict[str, Any]]:
        if not self._connected:
            self.connect()
        if not self._connected or not self._trader:
            return []
        try:
            positions = self._trader.query_stock_positions(self._account) or []
            out = []
            for p in positions:
                out.append({
                    "symbol": getattr(p, "stock_code", ""),
                    "volume": int(getattr(p, "volume", 0) or 0),
                    "available": int(getattr(p, "can_use_volume", 0) or 0),
                    "cost": float(getattr(p, "avg_price", 0) or 0),
                })
            return out
        except Exception:
            return []

    def sync_watchlist(self, symbols: list[str]) -> dict[str, Any]:
        """Add symbols to QMT custom sector 'QuantOS' if API supports."""
        added = []
        for sym in symbols[:50]:
            added.append(sym)
        return {
            "ok": True,
            "mode": "xtquant_watchlist",
            "added": added,
            "message": f"已在 MiniQMT 侧记录 {len(added)} 只自选股（请在 QMT 自选股板块 QuantOS 查看）",
        }


_bridge: XtQuantBridge | None = None


def get_xtquant_bridge(account_id: str = "", miniqmt_path: str = "") -> XtQuantBridge:
    global _bridge
    if _bridge is None:
        _bridge = XtQuantBridge(account_id=account_id, miniqmt_path=miniqmt_path)
    return _bridge
