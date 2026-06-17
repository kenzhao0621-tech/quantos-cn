"""Broker capability wizard — honest status, no fake connections."""

from __future__ import annotations

from typing import Any

BROKER_STATUSES = {
    "PaperGateway": {"status": "SIMULATION_READY", "real_orders": False},
    "ShadowGateway": {"status": "SIMULATION_READY", "real_orders": False, "zero_real_orders_sent": True},
    "ManualConfirmGateway": {"status": "LIVE_REVIEW_REQUIRED", "real_orders": False},
    "ReadOnlyGateway": {"status": "NOT_CONFIGURED", "real_orders": False},
    "XTPGateway": {"status": "NOT_CONFIGURED", "real_orders": False},
    "QMTGateway": {"status": "NOT_CONFIGURED", "real_orders": False},
    "PTradeGateway": {"status": "NOT_CONFIGURED", "real_orders": False},
    "TORAGateway": {"status": "NOT_CONFIGURED", "real_orders": False},
}


def broker_wizard_state() -> dict[str, Any]:
    return {
        "real_execution_mode": "MANUAL_CONFIRM_ONLY",
        "real_money_execution_disabled": True,
        "live_execution": "LIVE_DISABLED",
        "gateways": BROKER_STATUSES,
        "user_checklist": [
            "确认券商支持官方 API（XTP/TORA/QMT/PTrade）",
            "申请只读账户权限（余额/持仓/委托/成交）",
            "安装券商客户端或 MiniQMT",
            "配置行情权限（Level-1/Level-2）",
            "申请仿真账户（如有）",
            "在 config/brokers.yaml 填写 endpoint 与 account_id（勿提交密钥到 git）",
            "运行 make broker-readonly-test 验证只读连接",
            "经人工审核后方可进入 LIMITED_LIVE_REVIEW_REQUIRED",
        ],
        "note": "真实券商未连接无法通过纯代码修复 — 需用户授权与 API  entitlement",
    }


def readonly_connect_wizard(broker: str, config: dict[str, Any]) -> dict[str, Any]:
    """Simulate wizard step — records intent only, no live connection."""
    st = BROKER_STATUSES.get(broker, {"status": "NOT_CONFIGURED"})
    if st["status"] == "NOT_CONFIGURED":
        return {
            "broker": broker,
            "status": "NOT_CONFIGURED",
            "connected": False,
            "message": f"{broker} 未配置 — 需官方 API 凭证",
        }
    return {
        "broker": broker,
        "status": st["status"],
        "connected": False,
        "config_received": bool(config),
        "message": "向导已记录 — 只读连接需用户提供的官方 API",
    }
