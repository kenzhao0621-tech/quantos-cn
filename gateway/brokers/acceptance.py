"""Full broker capability acceptance — multi-broker matrix with honest scoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

from gateway.brokers.broker_launcher import build_broker_urls, is_browser_broker, launch_cn_broker
from gateway.brokers.cn_broker_registry import BROWSER_BROKER_IDS, CN_BROKER_ECOSYSTEM
from gateway.brokers.connection_manager import load_broker_config, save_broker_config, test_broker_connection
from gateway.brokers.unified_bridge import broker_session_status, place_real_order
from gateway.brokers.xtquant_bridge import detect_miniqmt_paths, xtquant_available
from gateway.config import ROOT
from gateway.live_trading.gates import load_gates

REPORT_PATH = ROOT / "data" / "gateway" / "broker_capability_acceptance.json"


def _check_browser_broker(broker_id: str) -> dict[str, Any]:
    spec = CN_BROKER_ECOSYSTEM[broker_id]
    urls = build_broker_urls(broker_id, symbol="600000.SH", name="浦发银行")
    checks: dict[str, Any] = {
        "broker_id": broker_id,
        "label": spec["label"],
        "urls_ok": bool(urls.get("trade_login")),
        "quote_ok": bool(urls.get("quote")),
        "connect_ok": False,
        "launch_ok": False,
        "submit_handoff_ok": False,
        "watchlist_sync_ok": False,
        "status": "FAIL",
    }
    if not checks["urls_ok"]:
        checks["error"] = "missing trade_login url"
        return checks

    save_broker_config({"active_broker": broker_id})
    conn = test_broker_connection()
    checks["connect_ok"] = conn.get("connected") and conn.get("status") == "BROKER_WEB_READY"
    checks["connect_status"] = conn.get("status")

    with patch("gateway.brokers.broker_launcher.webbrowser.open", return_value=True):
        launch = launch_cn_broker(broker_id, target="trade_login")
        checks["launch_ok"] = launch.get("ok", False)
        checks["launch_url"] = launch.get("url", "")

    with patch("gateway.brokers.unified_bridge.launch_cn_broker") as mock_launch:
        mock_launch.return_value = {
            "ok": True,
            "url": urls["trade_login"],
            "broker_label": spec["label"],
            "urls": urls,
            "next_steps": ["登录", "买入"],
            "message": "mock",
        }
        with patch("gateway.brokers.unified_bridge.can_submit_live_order") as mock_gate:
            mock_gate.return_value = {"allowed": True, "blockers": [], "gates": load_gates().to_dict()}
            order = place_real_order(
                symbol="600000.SH",
                name="浦发银行",
                side="BUY",
                quantity=100,
                limit_price=10.0,
                user_confirmed=True,
            )
            checks["submit_handoff_ok"] = order.get("ok") and order.get("handoff", {}).get("mode") == "broker_browser"

    with patch("gateway.brokers.unified_bridge.launch_cn_broker") as mock_sync:
        mock_sync.return_value = {"ok": True, "broker_label": spec["label"]}
        from gateway.brokers.unified_bridge import sync_watchlist_to_broker
        sync = sync_watchlist_to_broker("acceptance", [{"symbol": "600000.SH", "name": "浦发银行"}])
        checks["watchlist_sync_ok"] = sync.get("ok") and sync.get("mode") == "broker_quote_tabs"

    passed = sum(1 for k in ("urls_ok", "quote_ok", "connect_ok", "launch_ok", "submit_handoff_ok", "watchlist_sync_ok") if checks[k])
    checks["score_pct"] = round(100 * passed / 6)
    checks["status"] = "PASS" if passed == 6 else ("PARTIAL" if passed >= 4 else "FAIL")
    return checks


def _check_qmt_path() -> dict[str, Any]:
    xt = xtquant_available("")
    paths = detect_miniqmt_paths()
    runtime_ok = False
    runtime_error = ""
    try:
        from xtquant.xttrader import XtQuantTrader  # noqa: F401
        runtime_ok = True
    except Exception as exc:
        runtime_error = str(exc)[:200]

    cfg = load_broker_config()
    save_broker_config({**cfg.to_dict(), "active_broker": "qmt_local"})
    conn = test_broker_connection()

    return {
        "broker_id": "qmt_local",
        "label": "MiniQMT / xtquant",
        "package_installed": xt.get("package_installed", False),
        "runtime_ready": runtime_ok,
        "runtime_error": runtime_error,
        "client_paths": paths,
        "connect_status": conn.get("status"),
        "connect_message": conn.get("message"),
        "real_connect_ok": conn.get("real_orders", False),
        "platform_note": xt.get("platform_note"),
        "install_steps": [
            "Windows: 向券商申请 MiniQMT → 安装 QMT → 极简模式登录",
            "QMT 设置 → 模型设置 → 下载 Python 库",
            "复制 bin.x64/Lib/site-packages/xtquant 到本机 Python 或设置 MINIQMT_PATH",
            "macOS: Parallels/UTM 虚拟机内完成上述步骤，本机 Gateway 走浏览器券商路径",
        ],
        "status": "PASS" if conn.get("real_orders") else ("PARTIAL" if runtime_ok or paths else "BLOCKED"),
        "score_pct": 100 if conn.get("real_orders") else (40 if runtime_ok else 20 if xt.get("package_installed") else 0),
    }


def run_broker_acceptance(*, save: bool = True) -> dict[str, Any]:
    browser_results = [_check_browser_broker(bid) for bid in sorted(BROWSER_BROKER_IDS)]
    qmt_result = _check_qmt_path()
    session = broker_session_status()

    browser_pass = sum(1 for r in browser_results if r["status"] == "PASS")
    browser_avg = round(sum(r["score_pct"] for r in browser_results) / max(len(browser_results), 1))
    gates = load_gates().to_dict()

    # Weight: 9 browser platforms 70%, qmt 20%, session/api 10%
    overall = round(browser_avg * 0.7 + qmt_result["score_pct"] * 0.2 + (10 if session.get("gates") else 0))
    verdict = "FULL_PASS" if browser_pass == len(browser_results) and qmt_result.get("real_connect_ok") else (
        "BROWSER_FULL_QMT_PENDING" if browser_pass == len(browser_results) else "PARTIAL"
    )

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "overall_score_pct": overall,
        "browser_brokers": {
            "total": len(browser_results),
            "pass": browser_pass,
            "average_score_pct": browser_avg,
            "brokers": browser_results,
        },
        "qmt_xtquant": qmt_result,
        "session_snapshot": {
            "active_broker": session.get("active_broker"),
            "real_money_enabled": gates.get("real_money_enabled"),
            "xtquant": session.get("xtquant"),
        },
        "capabilities": {
            "multi_broker_select": len(CN_BROKER_ECOSYSTEM),
            "browser_launch": browser_pass,
            "watchlist_sync": sum(1 for r in browser_results if r.get("watchlist_sync_ok")),
            "submit_order_handoff": sum(1 for r in browser_results if r.get("submit_handoff_ok")),
            "xtquant_real_orders": qmt_result.get("real_connect_ok", False),
        },
        "honest_limits": [
            "pip install xtquant 在 macOS 不完整，需 Windows MiniQMT 客户端目录中的完整 xtquant",
            "浏览器券商路径为真实官方 URL 跳转，下单须在券商平台本人确认",
            "涨乐财富通网页交易需 IE/360 兼容模式或 App 扫码",
        ],
    }

    if save:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            __import__("json").dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return report
