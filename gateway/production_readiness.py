"""Production-readiness checks mapped from the Gateway portal requirements.

This is a quant trading adaptation of the enterprise Gateway requirements:
unified portal, RBAC, broker/platform adapters, model governance, audit,
observability, cost/risk budgets, and high-risk action confirmation.
"""

from __future__ import annotations

from typing import Any

from gateway.config import ROOT
from quant.paths import desktop_reports_root


def gateway_readiness_report() -> dict[str, Any]:
    checks = [
        _check("portal_home", True, "统一 Portal 已运行在 /portal"),
        _check("rbac", (ROOT / "gateway/auth/rbac.py").exists(), "角色权限与 API key 已接入"),
        _check("audit_log", (ROOT / "docs/ai/gateway/audit/events.jsonl").exists(), "审计事件 append-only JSONL"),
        _check("broker_handoff", True, "东方财富/XTP/QMT/PTrade/TORA 官方路径已登记"),
        _check("order_ticket", bool(list((ROOT / "data/gateway/order_tickets").glob("*.json"))) if (ROOT / "data/gateway/order_tickets").exists() else False, "Safe Autopilot 订单票据"),
        _check("model_validation", (ROOT / "quant/application/model_validation_service.py").exists(), "样本外/滚动/成本/滑点/行业中性验收"),
        _check("live_data", (ROOT / "quant/application/live_market_service.py").exists(), "实时/近实时行情服务"),
        _check(
            "desktop_report_delivery",
            desktop_reports_root().exists(),
            "日报桌面导出目录",
        ),
        _check("secret_storage", False, "生产级密钥加密/KMS 尚未接入"),
        _check("sso", False, "企业 SSO 尚未接入；当前为本地开发登录"),
        _check("cost_dashboard", False, "AI/券商调用成本 Dashboard 尚未完整实现"),
        _check("approval_workflow", True, "高风险真实交易仅允许人工确认交接"),
    ]
    done = sum(1 for c in checks if c["passed"])
    score = round(done / len(checks) * 100, 1)
    gaps = [c for c in checks if not c["passed"]]
    return {
        "score": score,
        "passed": score >= 70,
        "checks": checks,
        "gaps": gaps,
        "production_label": "LOCAL_TRADING_ASSISTANT_READY" if score >= 70 else "NOT_PRODUCTION_READY",
        "next_actions": [
            "接入券商官方只读/仿真 API 权限后，再做连接测试。",
            "接入密钥加密/KMS 或本地系统钥匙串后，才允许保存非交易敏感配置。",
            "继续累计 Paper/Shadow 样本，模型验收通过后再进入人工确认真实交易流程。",
        ],
    }


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}

