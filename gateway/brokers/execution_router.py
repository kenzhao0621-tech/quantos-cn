"""Multi-path broker execution router — Mac unattended auto with ordered fallbacks.

Path priority (Mac):
  1. remote_sidecar  — HTTP → Windows VM MiniQMT (true API auto)
  2. xtquant_local   — Windows native MiniQMT
  3. playwright_auto — saved session + fill + optional auto-submit (gated)
  4. qmt_csv_drop    — order file to MiniQMT inbox
  5. playwright_assist — pre-fill, user clicks confirm on broker page
  6. browser_launch  — open official URL only

One path failing does not stop the chain unless ``stop_on_first_error`` is set.
"""

from __future__ import annotations

import platform
from typing import Any

from gateway.brokers.broker_launcher import is_browser_broker, launch_cn_broker
from gateway.brokers.connection_manager import BrokerConfig, load_broker_config, test_broker_connection
from gateway.brokers.remote_sidecar import sidecar_configured, sidecar_place_order, test_sidecar_connection
from gateway.brokers.xtquant_bridge import detect_miniqmt_paths, xtquant_available
from gateway.live_trading.gates import ExecutionLevel, can_submit_live_order, can_submit_unattended_order, load_gates


def _platform() -> str:
    return platform.system().lower()


def list_execution_paths(cfg: BrokerConfig | None = None) -> list[dict[str, Any]]:
    """Return ordered execution paths with live availability probes."""
    cfg = cfg or load_broker_config()
    gates = load_gates()
    paths: list[dict[str, Any]] = []
    plat = _platform()

    if sidecar_configured(cfg):
        sc = test_sidecar_connection(cfg)
        paths.append({
            "path_id": "remote_sidecar",
            "label": "Mac → Sidecar → MiniQMT API",
            "unattended_capable": True,
            "available": sc.get("connected"),
            "status": sc.get("status"),
            "message": sc.get("message"),
            "priority": 1,
            "platforms": ["darwin", "linux", "windows"],
            "requires": ["sidecar_url", "account_id", "Windows VM MiniQMT logged in"],
        })

    xt = xtquant_available(cfg.qmt_order_dir or "")
    if cfg.active_broker == "qmt_local" or xt.get("runtime_ready"):
        paths.append({
            "path_id": "xtquant_local",
            "label": "本机 MiniQMT xtquant API",
            "unattended_capable": True,
            "available": bool(xt.get("runtime_ready") and cfg.account_id),
            "status": "XTQUANT_READY" if xt.get("runtime_ready") else "XTQUANT_NOT_READY",
            "message": xt.get("reason", ""),
            "priority": 2,
            "platforms": ["windows"],
            "requires": ["MINIQMT_PATH", "XTQUANT_ACCOUNT_ID"],
        })

    if is_browser_broker(cfg.active_broker):
        from gateway.brokers.playwright_assist import has_saved_session, session_status

        sess = session_status(cfg.active_broker)
        auto_ok = gates.execution_level >= ExecutionLevel.CONDITIONAL_AUTO.value and gates.real_money_enabled
        paths.append({
            "path_id": "playwright_auto",
            "label": "Playwright 会话自动填单+提交",
            "unattended_capable": auto_ok,
            "available": sess.get("saved") and sess.get("playwright_ready"),
            "status": "SESSION_READY" if sess.get("saved") else "NEED_LOGIN",
            "message": "需先「登录一次」；门控须启用 CONDITIONAL_AUTO",
            "priority": 3,
            "platforms": ["darwin", "windows", "linux"],
            "requires": ["browser session", "execution_level>=3", "real_money_enabled"],
        })
        paths.append({
            "path_id": "playwright_assist",
            "label": "Playwright 预填（人工点确认）",
            "unattended_capable": False,
            "available": sess.get("playwright_ready", True),
            "status": "ASSIST",
            "message": "打开券商页并预填，你在官方页面点买入",
            "priority": 5,
            "platforms": ["darwin", "windows", "linux"],
            "requires": ["browser session recommended"],
        })

    if cfg.qmt_order_dir or cfg.active_broker == "qmt_local":
        paths.append({
            "path_id": "qmt_csv_drop",
            "label": "QMT 订单 CSV 落盘",
            "unattended_capable": True,
            "available": bool(cfg.qmt_order_dir),
            "status": "CSV_DIR" if cfg.qmt_order_dir else "NO_DIR",
            "message": "写入 MiniQMT 监控目录，由 QMT 策略/人工确认",
            "priority": 4,
            "platforms": ["darwin", "windows"],
            "requires": ["qmt_order_dir"],
        })

    paths.append({
        "path_id": "browser_launch",
        "label": "打开官方券商页面",
        "unattended_capable": False,
        "available": True,
        "status": "FALLBACK",
        "message": "最终兜底：仅打开 URL",
        "priority": 99,
        "platforms": ["darwin", "windows", "linux"],
        "requires": [],
    })

    paths.sort(key=lambda x: x["priority"])
    return paths


def execute_order(
    *,
    symbol: str,
    name: str,
    side: str,
    quantity: int,
    limit_price: float,
    user_id: str = "default",
    user_confirmed: bool = False,
    unattended: bool = False,
    source: str = "screener",
) -> dict[str, Any]:
    """Execute via multi-path router. ``unattended=True`` skips per-order user confirm when gates allow."""
    if quantity < 100 or quantity % 100 != 0:
        return {
            "ok": False,
            "error": {"code": "INVALID_LOT", "message": "A股买入数量须为 100 股整数倍"},
            "paths_tried": [],
        }

    notional = round(limit_price * quantity, 2)
    if unattended:
        gate = can_submit_unattended_order(notional_cny=notional)
    else:
        gate = can_submit_live_order(notional_cny=notional)
        if not user_confirmed:
            gate["blockers"].append("USER_CONFIRM_REQUIRED")
            gate["allowed"] = False

    if not gate["allowed"]:
        return {
            "ok": False,
            "error": {"code": "LIVE_ORDER_BLOCKED", "message": "门控未通过"},
            "blockers": gate["blockers"],
            "gates": gate["gates"],
            "paths_tried": [],
            "user_action": "在券商连接页启用门控并选择 CONDITIONAL_AUTO 无人值守模式",
        }

    cfg = load_broker_config()
    paths_tried: list[dict[str, Any]] = []
    order_ctx = {
        "symbol": symbol,
        "name": name,
        "side": side,
        "quantity": quantity,
        "limit_price": limit_price,
        "user_id": user_id,
        "unattended": unattended,
        "source": source,
    }

    for path in list_execution_paths(cfg):
        pid = path["path_id"]
        if unattended and not path.get("unattended_capable") and pid not in ("playwright_assist", "browser_launch"):
            continue
        attempt = _try_path(pid, cfg=cfg, order_ctx=order_ctx, unattended=unattended)
        paths_tried.append({"path_id": pid, **attempt})
        if attempt.get("ok"):
            attempt["paths_tried"] = paths_tried
            attempt["winning_path"] = pid
            _ledger(order_ctx, attempt, pid)
            return attempt

    return {
        "ok": False,
        "error": {"code": "ALL_PATHS_FAILED", "message": "所有执行路径均失败"},
        "paths_tried": paths_tried,
        "user_action": "配置 Sidecar（推荐）或完成浏览器登录后重试",
    }


def _try_path(
    path_id: str,
    *,
    cfg: BrokerConfig,
    order_ctx: dict[str, Any],
    unattended: bool,
) -> dict[str, Any]:
    sym = order_ctx["symbol"]
    name = order_ctx["name"]
    side = order_ctx["side"]
    qty = order_ctx["quantity"]
    price = order_ctx["limit_price"]
    uid = order_ctx["user_id"]

    if path_id == "remote_sidecar" and sidecar_configured(cfg):
        from gateway.brokers.local_auth import require_local_consent
        block = require_local_consent(uid) if cfg.active_broker == "mac_sidecar" else None
        if block:
            return {"ok": False, "error": block}
        r = sidecar_place_order(
            symbol=sym, side=side, quantity=qty, limit_price=price,
            account_id=cfg.account_id, remark=f"QuantOS-{uid}", cfg=cfg,
        )
        if r.get("ok"):
            r["handoff"] = {"mode": "remote_sidecar", "sidecar_url": cfg.sidecar_url}
            r["legal_boundary"] = "REAL_BROKER_ORDER_UNATTENDED"
        return r

    if path_id == "xtquant_local" and cfg.active_broker == "qmt_local":
        from gateway.brokers.local_auth import require_local_consent
        from gateway.brokers.xtquant_bridge import get_xtquant_bridge

        block = require_local_consent(uid)
        if block:
            return {"ok": False, "error": block}
        xt = xtquant_available(cfg.qmt_order_dir or "")
        if not xt.get("runtime_ready") or not cfg.account_id:
            return {"ok": False, "error": {"code": "XTQUANT_NOT_READY", "message": xt.get("reason", "")}}
        bridge = get_xtquant_bridge(account_id=cfg.account_id, miniqmt_path=xt.get("miniqmt_path", ""))
        r = bridge.place_order(symbol=sym, side=side, quantity=qty, limit_price=price, remark=f"QuantOS-{uid}")
        if r.get("ok"):
            r["handoff"] = {"mode": "xtquant_api"}
            r["legal_boundary"] = "REAL_BROKER_ORDER_UNATTENDED"
        return r

    if path_id == "playwright_auto" and is_browser_broker(cfg.active_broker):
        from gateway.brokers.playwright_assist import assist_place_order_auto

        return assist_place_order_auto(
            cfg.active_broker,
            symbol=sym, name=name, side=side, quantity=qty, limit_price=price,
            auto_submit=unattended,
        )

    if path_id == "qmt_csv_drop":
        from gateway.brokers.live_order import submit_live_order

        return submit_live_order(
            symbol=sym, name=name, side=side, quantity=qty, limit_price=price,
            user_confirmed=True, source=order_ctx["source"], user_id=uid,
        )

    if path_id == "playwright_assist" and is_browser_broker(cfg.active_broker):
        from gateway.brokers.playwright_assist import assist_place_order

        return assist_place_order(
            cfg.active_broker, symbol=sym, name=name, side=side, quantity=qty, limit_price=price,
        )

    if path_id == "browser_launch":
        r = launch_cn_broker(
            cfg.active_broker, symbol=sym, name=name, side=side,
            quantity=qty, limit_price=price, target="trade_login",
        )
        return {
            "ok": bool(r.get("ok")),
            "handoff": {"mode": "browser_launch", "web_url": r.get("url")},
            "message": r.get("message", ""),
            "legal_boundary": "USER_MUST_CONFIRM_ON_BROKER",
        }

    return {"ok": False, "error": {"code": "PATH_SKIP", "message": f"path {path_id} not applicable"}}


def _ledger(ctx: dict[str, Any], result: dict[str, Any], path_id: str) -> None:
    try:
        from gateway.brokers.operations_ledger import append_operation
        append_operation(
            mode="real",
            action="order_execute" if ctx.get("unattended") else "order_assist",
            user_id=ctx["user_id"],
            symbol=ctx["symbol"],
            name=ctx["name"],
            details={
                "path": path_id,
                "side": ctx["side"],
                "quantity": ctx["quantity"],
                "limit_price": ctx["limit_price"],
                "unattended": ctx.get("unattended"),
                "status": result.get("order", {}).get("status") or result.get("handoff", {}).get("mode"),
            },
        )
    except Exception:
        pass
