"""Broker capability wizard — honest status, no fake connections."""

from __future__ import annotations

from typing import Any

BROKER_STATUSES = {
    "PaperGateway": {"status": "SIMULATION_READY", "real_orders": False},
    "ShadowGateway": {"status": "SIMULATION_READY", "real_orders": False, "zero_real_orders_sent": True},
    "ManualConfirmGateway": {"status": "LIVE_REVIEW_REQUIRED", "real_orders": False},
    "ReadOnlyGateway": {"status": "NOT_CONFIGURED", "real_orders": False},
    "EastmoneyGateway": {"status": "OFFICIAL_HANDOFF", "real_orders": False},
    "XTPGateway": {"status": "NOT_CONFIGURED", "real_orders": False},
    "QMTGateway": {"status": "NOT_CONFIGURED", "real_orders": False},
    "PTradeGateway": {"status": "NOT_CONFIGURED", "real_orders": False},
    "TORAGateway": {"status": "NOT_CONFIGURED", "real_orders": False},
}

BROKER_PORTAL_LINKS = [
    {
        "name": "东方财富证券",
        "type": "官方网站 / 登录交易 / 开户与软件下载",
        "url": "https://www.18.cn/",
        "note": "东方财富证券官方站点。用户本人登录官方平台后，可按 QuantOS 订单票据手动确认交易。",
    },
    {
        "name": "东方财富 PC/APP 下载",
        "type": "官方交易客户端",
        "url": "https://www.18.cn/soft/",
        "note": "用于安装官方交易客户端；本系统不采集交易密码，不代替用户确认真实订单。",
    },
    {
        "name": "XTP 极速交易平台",
        "type": "官方 API / 仿真 / 只读",
        "url": "https://xtp.zts.com.cn/",
        "note": "中泰证券 XTP 官方站点；需要用户自行申请权限和账号。",
    },
    {
        "name": "MiniQMT / QMT",
        "type": "券商客户端 / 本地网关",
        "url": "https://www.myquant.cn/",
        "note": "迅投/券商分发的 MiniQMT/QMT 生态入口；具体版本以开户券商官方渠道为准。",
    },
    {
        "name": "PTrade",
        "type": "券商量化终端",
        "url": "https://www.hundsun.com/",
        "note": "恒生体系，通常由券商开通；需官方授权。",
    },
    {
        "name": "TORA",
        "type": "专业交易接入",
        "url": "https://www.tora.com/",
        "note": "机构交易系统方向；是否支持 A 股需以券商/厂商合同为准。",
    },
]


def broker_wizard_state() -> dict[str, Any]:
    return {
        "real_execution_mode": "MANUAL_CONFIRM_ONLY",
        "real_money_execution_disabled": True,
        "live_execution": "LIVE_DISABLED",
        "gateways": BROKER_STATUSES,
        "portal_links": BROKER_PORTAL_LINKS,
        "handoff_contract": {
            "supported": True,
            "description": "QuantOS 生成订单票据，用户在东方财富/XTP/QMT/PTrade/TORA 等官方平台人工确认。",
            "forbidden": "不保存交易密码，不绕过券商确认，不自动发送真实资金订单。",
        },
        "user_checklist": [
            "确认本人已完成券商开户、风险测评和交易权限开通",
            "确认券商支持官方 API（XTP/TORA/QMT/PTrade）",
            "若使用东方财富等网站/客户端，必须由用户本人登录官方平台",
            "申请只读账户权限（余额/持仓/委托/成交）",
            "安装券商客户端或 MiniQMT",
            "配置行情权限（Level-1/Level-2）",
            "申请仿真账户（如有）",
            "在 config/brokers.yaml 填写 endpoint 与 account_id（勿提交密钥到 git）",
            "运行 make broker-readonly-test 验证只读连接",
            "经人工审核后方可进入 LIMITED_LIVE_REVIEW_REQUIRED",
        ],
        "note": "真实券商接入必须走官方授权/客户端/人工确认；QuantOS 负责生成可审计订单票据和交接路径。",
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
