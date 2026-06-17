"""Live order handoff — QMT file drop & Eastmoney manual path (user-confirmed, no auto wire transfer)."""

from __future__ import annotations

import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.brokers.connection_manager import load_broker_config, test_broker_connection
from gateway.config import ROOT
from gateway.live_trading.gates import can_submit_live_order, load_gates

ORDER_LOG = ROOT / "data" / "gateway" / "live_orders.jsonl"


def submit_live_order(
    *,
    symbol: str,
    name: str,
    side: str,
    quantity: int,
    limit_price: float,
    user_confirmed: bool,
    source: str = "screener",
    user_id: str = "default",
) -> dict[str, Any]:
    if quantity < 100 or quantity % 100 != 0:
        return {
            "ok": False,
            "error": {"code": "INVALID_LOT", "message": "A股买入数量须为 100 股整数倍"},
            "user_action": "请调整数量为 100、200、300…",
        }
    notional = round(limit_price * quantity, 2)
    gate = can_submit_live_order(notional_cny=notional)
    if not user_confirmed:
        gate["blockers"].append("USER_CONFIRM_REQUIRED")
        gate["allowed"] = False
    if not gate["allowed"]:
        return {
            "ok": False,
            "error": {"code": "LIVE_ORDER_BLOCKED", "message": "真实下单门控未通过"},
            "blockers": gate["blockers"],
            "user_action": _blocker_action(gate["blockers"]),
            "gates": gate["gates"],
        }

    cfg = load_broker_config()
    from gateway.brokers.local_auth import require_local_consent
    consent_block = require_local_consent(user_id)
    if consent_block and cfg.active_broker == "qmt_local":
        return {"ok": False, "error": consent_block, "user_action": consent_block.get("user_action", "")}

    conn = test_broker_connection(cfg)
    order_id = str(uuid.uuid4())[:8]
    record = {
        "order_id": order_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "name": name,
        "side": side,
        "quantity": quantity,
        "limit_price": limit_price,
        "notional_cny": notional,
        "broker": cfg.active_broker,
        "source": source,
        "status": "PENDING_USER_BROKER_CONFIRM",
    }

    handoff: dict[str, Any] = {"mode": cfg.active_broker}
    if cfg.active_broker == "qmt_local" and conn.get("connected"):
        path = _export_qmt_single(record, cfg)
        record["status"] = "QMT_FILE_DROPPED"
        handoff = {
            "mode": "qmt_csv_drop",
            "file": str(path),
            "message": f"订单文件已写入 QMT 目录：{path}。请在 MiniQMT 中确认并提交。",
        }
    elif cfg.active_broker == "eastmoney_manual":
        portal_url = "https://www.18.cn/"
        handoff = {
            "mode": "manual_web",
            "portal_url": portal_url,
            "steps": [
                f"打开东方财富官方 App 或 {portal_url}",
                f"登录账号 {cfg.account_id or '（你的资金账号）'}",
                f"买入 {name or symbol}（{symbol}）",
                f"限价 ¥{limit_price:.2f}，数量 {quantity} 股",
                "核对无误后点击「买入」——必须由你本人确认",
            ],
        }
    elif cfg.active_broker == "xtp_readonly":
        return {
            "ok": False,
            "error": {"code": "XTP_READONLY", "message": "当前 XTP 配置为只读探测，不支持发单"},
            "user_action": "请改用 QMT 订单文件或东方财富人工确认路径",
        }
    else:
        return {
            "ok": False,
            "error": {"code": "BROKER_NOT_READY", "message": conn.get("message") or "券商未配置"},
            "user_action": "请在「券商」页选择 QMT 或东方财富并测试连接",
        }

    ORDER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ORDER_LOG.open("a", encoding="utf-8") as f:
        import json
        f.write(json.dumps({**record, "handoff": handoff}, ensure_ascii=False) + "\n")

    return {"ok": True, "order": record, "handoff": handoff, "legal_boundary": "USER_MUST_CONFIRM_ON_BROKER"}


def _export_qmt_single(record: dict[str, Any], cfg: Any) -> Path:
    drop = Path(cfg.qmt_order_dir).expanduser()
    drop.mkdir(parents=True, exist_ok=True)
    path = drop / f"quantos_{record['order_id']}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["证券代码", "买卖方向", "数量", "限价", "备注"])
        sym = record["symbol"].split(".")[0]
        w.writerow([sym, "买入" if record["side"] == "BUY" else "卖出", record["quantity"], record["limit_price"], f"QuantOS-{record['order_id']}"])
    return path


def _blocker_action(blockers: list[str]) -> str:
    if "LEGAL_REVIEW_REQUIRED" in blockers:
        return "管理员需在券商页完成合规确认（LEGAL_REVIEW）"
    if "USER_RISK_NOT_CONFIRMED" in blockers:
        return "请勾选「我已理解投资风险」并保存实盘门控"
    if "USER_CONFIRM_REQUIRED" in blockers:
        return "提交前请勾选本次订单确认框"
    if "REAL_MONEY_DISABLED" in blockers:
        return "请在券商页启用「受控真实下单」并配置连接"
    return "请检查券商连接与实盘门控设置"
