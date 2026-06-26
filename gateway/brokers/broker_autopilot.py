"""One-shot broker connect — login, watchlist sync, fill export. Minimal manual steps."""

from __future__ import annotations

from typing import Any

from gateway.brokers.broker_launcher import build_broker_urls, is_browser_broker, launch_cn_broker
from gateway.brokers.cn_broker_registry import CN_BROKER_ECOSYSTEM
from gateway.brokers.connection_manager import BrokerConfig, load_broker_config, save_broker_config, test_broker_connection
from gateway.brokers.playwright_assist import (
    assist_sync_watchlist,
    has_saved_session,
    run_login_assist,
    session_status,
)
from gateway.screener.watchlist import list_watchlist


def _broker_label(broker_id: str) -> str:
    return (CN_BROKER_ECOSYSTEM.get(broker_id) or {}).get("label", broker_id)


def run_connect_flow(
    *,
    broker_id: str | None = None,
    user_id: str = "default",
    open_login: bool = True,
    assist_login: bool = False,
    sync_watchlist: bool = True,
    wait_seconds: int = 120,
) -> dict[str, Any]:
    """Save broker → return official login URL (user browser). Playwright only if assist_login=True."""
    cfg = load_broker_config()
    bid = broker_id or cfg.active_broker
    if bid not in CN_BROKER_ECOSYSTEM:
        bid = "eastmoney_manual"

    save_broker_config({
        "active_broker": bid,
        "readonly": bid in ("paper_only", "xtp_readonly"),
    })
    cfg = load_broker_config()
    label = _broker_label(bid)
    urls = build_broker_urls(bid)
    login_url = urls.get("trade_login") or urls.get("portal", "")

    steps: list[str] = []
    result: dict[str, Any] = {
        "ok": True,
        "broker_id": bid,
        "broker_label": label,
        "login_url": login_url,
        "mode": "connect_flow",
    }

    if not is_browser_broker(bid):
        conn = test_broker_connection(cfg)
        result.update({
            "connection": conn,
            "message": conn.get("message", f"{label} 非浏览器券商，请按连接测试结果配置"),
            "steps": [conn.get("message", "")],
        })
        return result

    # Return URL for the user's own browser (avoids Playwright 403 from broker WAF)
    launch = launch_cn_broker(bid, target="trade_login")
    result["launch"] = launch
    result["client_url"] = launch.get("url") or login_url
    from gateway.brokers.login_redirect import issue_login_redirect

    result["login_redirect_token"] = issue_login_redirect(result["client_url"])
    result["login_redirect_path"] = f"/api/v1/brokers/login-redirect/{result['login_redirect_token']}"

    session_before = session_status(bid)
    login_result: dict[str, Any] = {"skipped": True}
    if assist_login:
        login_result = run_login_assist(bid, wait_seconds=wait_seconds)
        steps.append(login_result.get("message", "请在弹出浏览器完成登录"))
    elif open_login:
        steps.append(f"已在你的浏览器打开 {label} 官方登录页（请用本机 Chrome/Safari 登录，勿在自动化窗口操作）")
    elif session_before.get("saved"):
        steps.append("已检测到保存的登录会话，跳过重复登录")
        login_result = {"ok": True, "mode": "session_reuse", "message": "使用已保存会话"}

    result["login"] = login_result
    result["session"] = session_status(bid)

    sync_result: dict[str, Any] | None = None
    if sync_watchlist:
        items = list_watchlist(user_id)
        if items:
            from gateway.brokers.unified_bridge import sync_watchlist_to_broker
            sync_result = sync_watchlist_to_broker(user_id, items)
            steps.append(sync_result.get("message", "自选同步完成"))
        else:
            steps.append("收藏列表为空，选股后点 ★ 再同步")

    result["watchlist_sync"] = sync_result
    result["steps"] = steps
    result["message"] = (
        f"已连接 {label}。"
        + ("登录会话已保存。" if result["session"].get("saved") else "请完成浏览器登录。")
        + (f" 自选同步：{sync_result.get('message')}" if sync_result else "")
    )
    result["ready_for_trade"] = bool(result["session"].get("saved"))
    from gateway.brokers.waf_recovery import waf_recovery_for_broker

    result["waf_recovery"] = waf_recovery_for_broker(bid)
    result["open_url_preferred"] = (
        (waf_recovery_for_broker(bid).get("fallback_urls") or [{}])[0].get("url")
        or result.get("client_url")
    )
    return result


def run_post_login_automation(
    *,
    user_id: str = "default",
    export_fills: bool = True,
) -> dict[str, Any]:
    """After login: sync watchlist + try export fills from broker web."""
    cfg = load_broker_config()
    bid = cfg.active_broker
    if not is_browser_broker(bid):
        return {"ok": False, "error": "NOT_BROWSER_BROKER"}

    from gateway.brokers.playwright_assist import auto_export_fills, auto_import_watchlist_csv

    items = list_watchlist(user_id)
    out: dict[str, Any] = {"ok": True, "broker_id": bid, "actions": []}

    if items:
        from gateway.brokers.unified_bridge import sync_watchlist_to_broker
        sync = sync_watchlist_to_broker(user_id, items)
        out["actions"].append({"action": "watchlist_sync", "result": sync})

    imp = auto_import_watchlist_csv(bid, user_id)
    if imp.get("attempted"):
        out["actions"].append({"action": "csv_import", "result": imp})

    if export_fills:
        exp = auto_export_fills(bid)
        out["actions"].append({"action": "fills_export", "result": exp})
        if exp.get("fills_imported"):
            out["fills_imported"] = exp.get("fills_imported", 0)

    out["message"] = "；".join(
        a["result"].get("message", "") for a in out["actions"] if a.get("result", {}).get("message")
    ) or "自动化步骤已执行"
    return out
