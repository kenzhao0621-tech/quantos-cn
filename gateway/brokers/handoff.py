"""Order ticket export and broker handoff artifacts."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT

EXPORT_DIR = ROOT / "data" / "gateway" / "order_exports"


def export_ticket_csv(ticket: dict[str, Any]) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    ticket_id = ticket.get("ticket_id", "unknown")
    path = EXPORT_DIR / f"{ticket_id}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["symbol", "side", "quantity", "price", "notional_cny", "sector", "score"])
        for line in ticket.get("lines", []):
            writer.writerow([
                line.get("symbol"),
                line.get("side"),
                line.get("quantity"),
                line.get("reference_price"),
                line.get("notional_cny"),
                line.get("sector", ""),
                line.get("score", ""),
            ])
    return path


def export_qmt_orders(ticket: dict[str, Any], *, drop_dir: Path | None = None) -> dict[str, Any]:
    """Write QMT-friendly CSV to export dir and optional user drop dir."""
    csv_path = export_ticket_csv(ticket)
    qmt_path = EXPORT_DIR / f"{ticket.get('ticket_id')}_qmt.csv"
    with qmt_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["证券代码", "买卖方向", "数量", "价格", "备注"])
        for line in ticket.get("lines", []):
            sym = str(line.get("symbol", "")).split(".")[0]
            writer.writerow([sym, "买入" if line.get("side") == "BUY" else "卖出", line.get("quantity"), line.get("reference_price"), f"QuantOS-{ticket.get('ticket_id')}"])
    copied_to = None
    if drop_dir:
        drop = Path(drop_dir).expanduser()
        drop.mkdir(parents=True, exist_ok=True)
        target = drop / f"quantos_{ticket.get('ticket_id')}.csv"
        target.write_text(qmt_path.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
        copied_to = str(target)
    return {"csv_path": str(csv_path.relative_to(ROOT)), "qmt_path": str(qmt_path.relative_to(ROOT)), "qmt_drop_path": copied_to}


def handoff_instructions(ticket: dict[str, Any], broker: str) -> list[str]:
    lines = ticket.get("lines") or []
    if not lines:
        return ["当前票据无可执行行 — 请调整资金/价格区间后重新生成。"]
    if broker == "qmt_local":
        return [
            "1. 在 MiniQMT/QMT 中确认已登录仿真或实盘账户（需券商开通）。",
            "2. 点击「导出 QMT 订单文件」或检查配置的订单目录。",
            "3. 在 QMT 导入 CSV / 手工核对后提交委托。",
            "4. 回到本页点击「我已提交到券商」记录审计。",
        ]
    if broker == "xtp_readonly":
        return [
            "1. XTP 只读/仿真连接通过后，可在券商官方终端核对持仓。",
            "2. 本系统生成的票据需通过 XTP 交易 API 由你方授权程序提交（本门户不自动发单）。",
        ]
    return [
        "1. 打开东方财富官方客户端或 https://www.18.cn/ 登录你的账户。",
        "2. 按票据逐笔输入：代码、买入、数量、限价（参考价）。",
        "3. 在券商界面亲自确认提交 — 本软件不会代你点击确认。",
        "4. 完成后可点击「我已提交到券商」留痕。",
    ]


def record_handoff_ack(ticket_id: str, *, broker: str, user_note: str = "") -> dict[str, Any]:
    path = ROOT / "data" / "gateway" / "handoff_ack.jsonl"
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ticket_id": ticket_id,
        "broker": broker,
        "user_note": user_note,
        "ack": "USER_CONFIRMED_BROKER_SUBMIT",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row
