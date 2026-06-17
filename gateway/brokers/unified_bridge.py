"""Unified broker bridge — routes to xtquant, EMT, CSV drop, or Eastmoney launcher."""

from __future__ import annotations

from typing import Any

from gateway.brokers.broker_launcher import is_browser_broker, launch_cn_broker
from gateway.brokers.connection_manager import BrokerConfig, load_broker_config, test_broker_connection
from gateway.brokers.live_order import submit_live_order as _csv_handoff_order
from gateway.brokers.playwright_assist import assist_place_order, has_saved_session, run_login_assist, session_status
from gateway.brokers.remote_sidecar import (
    sidecar_configured,
    sidecar_place_order,
    sidecar_sync_watchlist,
    test_sidecar_connection,
)
from gateway.brokers.xtquant_bridge import detect_miniqmt_paths, get_xtquant_bridge, xtquant_available
from gateway.live_trading.gates import can_submit_live_order, load_gates


def _blocker_hint(blockers: list[str]) -> str:
    if "REAL_MONEY_DISABLED" in blockers:
        return "请在券商页勾选门控三项并保存"
    if "USER_CONFIRM_REQUIRED" in blockers:
        return "提交前请确认本次真实下单"
    if "LOCAL_CONSENT_REQUIRED" in blockers:
        return "请勾选本机授权并保存"
    if blockers:
        return f"门控拦截: {', '.join(blockers)}"
    return ""


def broker_session_status(cfg: BrokerConfig | None = None) -> dict[str, Any]:
    cfg = cfg or load_broker_config()
    gates = load_gates()
    base = test_broker_connection(cfg)
    xt = xtquant_available(cfg.qmt_order_dir or "")
    session: dict[str, Any] = {
        "active_broker": cfg.active_broker,
        "gates": gates.to_dict(),
        "real_money_enabled": gates.real_money_enabled,
        "xtquant": xt,
        "detected_miniqmt": detect_miniqmt_paths(),
        "connection": base,
        "sidecar_configured": sidecar_configured(cfg),
        "browser_session": session_status(cfg.active_broker) if is_browser_broker(cfg.active_broker) else {},
    }
    if sidecar_configured(cfg):
        session["sidecar"] = test_sidecar_connection(cfg)
    from gateway.brokers.execution_router import list_execution_paths
    session["execution_paths"] = list_execution_paths(cfg)
    if cfg.active_broker == "qmt_local" and xt.get("runtime_ready") and cfg.account_id:
        bridge = get_xtquant_bridge(account_id=cfg.account_id, miniqmt_path=xt.get("miniqmt_path", ""))
        session["xtquant_session"] = bridge.connect()
    return session


def place_real_order(
    *,
    symbol: str,
    name: str,
    side: str,
    quantity: int,
    limit_price: float,
    user_confirmed: bool,
    user_id: str = "default",
    prefer_xtquant: bool = True,
    source: str = "screener",
    unattended: bool = False,
) -> dict[str, Any]:
    from gateway.brokers.execution_router import execute_order
    from gateway.live_trading.gates import load_gates

    gates = load_gates()
    if unattended or (gates.unattended_auto_enabled and gates.execution_level >= 3):
        return execute_order(
            symbol=symbol,
            name=name,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            user_id=user_id,
            user_confirmed=user_confirmed,
            unattended=True,
            source=source,
        )
    return execute_order(
        symbol=symbol,
        name=name,
        side=side,
        quantity=quantity,
        limit_price=limit_price,
        user_id=user_id,
        user_confirmed=user_confirmed,
        unattended=False,
        source=source,
    )


def sync_watchlist_to_broker(user_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    cfg = load_broker_config()
    symbols = [it["symbol"] for it in items if it.get("symbol")]

    if sidecar_configured(cfg) and (cfg.active_broker == "mac_sidecar" or cfg.auto_trade_via_sidecar):
        sync = sidecar_sync_watchlist(symbols, cfg)
        if sync.get("ok"):
            from gateway.screener.watchlist import mark_items_synced
            from gateway.brokers.operations_ledger import append_operation
            mark_items_synced(user_id, sync.get("synced", symbols))
            append_operation(
                mode="real", action="watchlist_sync", user_id=user_id,
                details={"mode": sync.get("mode"), "count": len(symbols), "broker": cfg.active_broker},
            )
            return sync

    if cfg.active_broker == "qmt_local":
        xt = xtquant_available(cfg.qmt_order_dir or "")
        if xt.get("runtime_ready") and cfg.account_id:
            bridge = get_xtquant_bridge(account_id=cfg.account_id, miniqmt_path=xt.get("miniqmt_path", ""))
            conn = bridge.connect()
            if conn.get("ok"):
                result = bridge.sync_watchlist(symbols)
                if result.get("ok"):
                    from gateway.screener.watchlist import mark_items_synced
                    from gateway.brokers.operations_ledger import append_operation
                    mark_items_synced(user_id, symbols)
                    append_operation(mode="real", action="watchlist_sync", user_id=user_id, details=result)
                return result

    if is_browser_broker(cfg.active_broker):
        from gateway.brokers.playwright_assist import assist_sync_watchlist
        from gateway.screener.watchlist import mark_items_synced
        from gateway.brokers.operations_ledger import append_operation

        assist = assist_sync_watchlist(cfg.active_broker, items)
        synced_syms = assist.get("synced") or assist.get("opened") or []
        if assist.get("ok") and synced_syms:
            mark_items_synced(user_id, synced_syms)
        if assist.get("ok"):
            append_operation(
                mode="real",
                action="watchlist_sync",
                user_id=user_id,
                details={
                    "mode": assist.get("mode"),
                    "synced": assist.get("synced", []),
                    "opened": assist.get("opened", []),
                    "csv_file": assist.get("csv_file", ""),
                    "broker": cfg.active_broker,
                    "message": assist.get("message", ""),
                },
            )
            return assist

    from gateway.screener.watchlist import sync_watchlist_to_broker as file_sync
    return file_sync(user_id)
