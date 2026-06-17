"""Trading operations daily report — virtual (paper) vs real, intraday + close."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT / "docs" / "ai" / "daily-trading" / "daily"
DESKTOP_ROOT = Path.home() / "Desktop" / "China_A_Share_Daily_Reports"


def _slot_label(session: str) -> str:
    return {
        "pre_open": "开盘前",
        "morning": "上午盘中",
        "lunch": "午间",
        "afternoon": "下午盘中",
        "close": "收盘",
        "intraday": "盘中",
        "manual": "手动",
    }.get(session, session)


def generate_trading_ops_reports(
    trade_date: str | None = None,
    *,
    session: str = "close",
) -> dict[str, Any]:
    """Build JSON + HTML + PDF for paper and real trading ops."""
    from gateway.brokers.operations_ledger import summarize_day
    from quant.trading_report_renderer import (
        deliver_trading_pdfs,
        render_trading_ops_html,
        write_trading_pdf,
    )

    summary = summarize_day(trade_date, session=session)
    d = summary["trade_date"]
    slot = session.upper()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Any] = {"trade_date": d, "session": session, "modes": {}}

    for mode in ("paper", "real"):
        label = "虚拟盘" if mode == "paper" else "实操盘"
        base = f"{d}_{slot}_{mode.upper()}_OPS"
        json_path = DAILY_DIR / f"{base}.json"
        html_path = DAILY_DIR / f"{base}.html"
        pdf_path = DAILY_DIR / f"{base}.pdf"

        payload = {
            **summary,
            "report_mode": mode,
            "report_label": label,
            "session_label": _slot_label(session),
            "title": f"{label}操作日报 — {d} {_slot_label(session)}",
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        html = render_trading_ops_html(payload, mode=mode)
        html_path.write_text(html, encoding="utf-8")
        pdf_ok = write_trading_pdf(html_path, pdf_path, payload)

        paths["modes"][mode] = {
            "json": str(json_path),
            "html": str(html_path),
            "pdf": str(pdf_path) if pdf_ok else "",
            "pdf_ok": pdf_ok,
            "label": label,
        }

    paths["desktop"] = deliver_trading_pdfs(d, paths["modes"])
    meta_path = DAILY_DIR / f"{d}_TRADING_OPS_META.json"
    meta_path.write_text(json.dumps(paths, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["meta"] = str(meta_path)
    return paths
