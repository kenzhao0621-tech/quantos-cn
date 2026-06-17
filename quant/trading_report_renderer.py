"""HTML/PDF renderer for paper vs real trading operations reports."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = Path.home() / "Desktop" / "China_A_Share_Daily_Reports"


def _fmt_pct(v: Any) -> str:
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_cny(v: Any) -> str:
    try:
        return f"¥{float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _ops_rows(ops: list[dict[str, Any]]) -> str:
    if not ops:
        return "<tr><td colspan='5'>今日暂无系统记录的操作</td></tr>"
    rows = []
    for op in ops[-30:]:
        det = op.get("details") or {}
        msg = det.get("message") or det.get("mode") or op.get("action", "")
        rows.append(
            f"<tr><td>{op.get('ts','')[:19]}</td>"
            f"<td>{op.get('action','')}</td>"
            f"<td>{op.get('symbol','')}</td>"
            f"<td>{op.get('name','')}</td>"
            f"<td>{msg}</td></tr>"
        )
    return "".join(rows)


def render_trading_ops_html(summary: dict[str, Any], *, mode: str) -> str:
    d = summary.get("trade_date", "")
    label = summary.get("report_label", mode)
    session = summary.get("session_label", "")
    is_paper = mode == "paper"
    block = summary.get("paper" if is_paper else "real", {})
    watermark = "虚拟盘 · Paper/Shadow 模拟" if is_paper else "实操盘 · 券商真实操作记录"

    perf = block.get("performance") or {}
    ops = block.get("operations") or []

    sections = [
        f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>",
        f"<title>{label}操作日报</title>",
        "<style>",
        "body{font-family:'PingFang SC','Microsoft YaHei',sans-serif;margin:36px;color:#1a1a1a;font-size:13px;}",
        "h1{font-size:20px;border-bottom:2px solid #333;padding-bottom:8px;}",
        "h2{font-size:15px;margin-top:22px;color:#333;}",
        ".meta{color:#555;font-size:12px;}",
        ".kpi{display:flex;gap:16px;flex-wrap:wrap;margin:12px 0;}",
        ".kpi div{background:#f4f6fa;padding:10px 14px;border-radius:8px;min-width:120px;}",
        ".kpi b{display:block;font-size:18px;margin-top:4px;}",
        "table{border-collapse:collapse;width:100%;font-size:11px;}",
        "td,th{border:1px solid #ccc;padding:5px;text-align:left;}",
        ".watermark{position:fixed;bottom:16px;right:16px;opacity:0.3;font-size:10px;}",
        "@page{size:A4 portrait;margin:18mm;}",
        "</style></head><body>",
        f"<h1>{label}操作日报</h1>",
        f"<p class='meta'>日期 {d} · 时段 {session} · 生成 {summary.get('generated_at','')[:19]}</p>",
        f"<p class='meta'>{watermark}</p>",
        "<div class='kpi'>",
    ]

    if is_paper:
        sections += [
            f"<div>操作次数<b>{block.get('operation_count', 0)}</b></div>",
            f"<div>信号触发<b>{perf.get('triggered_count', 0)}</b></div>",
            f"<div>胜率<b>{perf.get('hit_rate', 0) * 100:.1f}%</b></div>",
            f"<div>平均收益<b>{_fmt_pct(perf.get('avg_return_pct'))}</b></div>",
            f"<div>权益估计<b>{_fmt_cny(block.get('equity_cny'))}</b></div>",
            f"<div>浮盈亏<b>{_fmt_cny(block.get('unrealized_pnl'))}</b></div>",
            "</div>",
            "<h2>今日 Paper 信号表现</h2><table><tr><th>标的</th><th>结果</th><th>收益</th><th>入场</th><th>出场</th><th>教训</th></tr>",
        ]
        for sig in (perf.get("signals") or [])[:15]:
            sections.append(
                f"<tr><td>{sig.get('symbol','')}</td><td>{sig.get('result','')}</td>"
                f"<td>{_fmt_pct(sig.get('return_pct'))}</td><td>{sig.get('entry_price','')}</td>"
                f"<td>{sig.get('exit','')}</td><td>{sig.get('lesson','')}</td></tr>"
            )
        sections.append("</table>")
        positions = block.get("positions") or []
        if positions:
            sections += ["<h2>模拟持仓</h2><table><tr><th>代码</th><th>数量</th><th>成本</th><th>市值</th><th>浮盈亏</th></tr>"]
            for p in positions:
                sections.append(
                    f"<tr><td>{p.get('symbol','')}</td><td>{p.get('quantity','')}</td>"
                    f"<td>{p.get('avg_cost','')}</td><td>{p.get('market_value','')}</td>"
                    f"<td>{p.get('unrealized_pnl','')}</td></tr>"
                )
            sections.append("</table>")
    else:
        sections += [
            f"<div>操作次数<b>{block.get('operation_count', 0)}</b></div>",
            f"<div>成交笔数<b>{block.get('fill_count', 0)}</b></div>",
            f"<div>成交金额<b>{_fmt_cny(block.get('notional_cny'))}</b></div>",
            "</div>",
            "<h2>券商成交导入</h2><table><tr><th>代码</th><th>方向</th><th>数量</th><th>价格</th><th>时间</th></tr>",
        ]
        for f in (block.get("fills") or [])[:20]:
            sections.append(
                f"<tr><td>{f.get('symbol','')}</td><td>{f.get('side','')}</td>"
                f"<td>{f.get('quantity','')}</td><td>{f.get('price','')}</td>"
                f"<td>{f.get('filled_at','')}</td></tr>"
            )
        sections.append("</table>")
        assist = block.get("assist_events") or []
        if assist:
            sections += ["<h2>浏览器助手记录</h2><table><tr><th>时间</th><th>代码</th><th>数量</th><th>限价</th><th>预填</th></tr>"]
            for a in assist:
                sections.append(
                    f"<tr><td>{a.get('ts','')[:19]}</td><td>{a.get('symbol','')}</td>"
                    f"<td>{a.get('quantity','')}</td><td>{a.get('limit_price','')}</td>"
                    f"<td>{'是' if a.get('filled') else '否'}</td></tr>"
                )
            sections.append("</table>")

    sections += [
        "<h2>系统操作明细</h2>",
        "<table><tr><th>时间</th><th>类型</th><th>代码</th><th>名称</th><th>说明</th></tr>",
        _ops_rows(ops),
        "</table>",
        "<h2>新手说明</h2>",
        "<ul>",
        "<li>虚拟盘：Paper/Shadow 模拟与研究信号，不涉及真实资金。</li>" if is_paper else "<li>实操盘：你在券商官方页面确认的真实委托与导入成交。</li>",
        "<li>收益率来自 PERFORMANCE_LEDGER（虚拟）或券商成交导入（实盘）。</li>" if is_paper else "<li>请在收盘后从券商导出成交 CSV 并导入系统以对账。</li>",
        "<li>本报告自动生成，可在 Portal「报告」页下载 PDF。</li>",
        "</ul>",
        f"<div class='watermark'>{watermark}</div>",
        "</body></html>",
    ]
    return "".join(sections)


def write_trading_pdf(html_path: Path, pdf_path: Path, payload: dict[str, Any]) -> bool:
    script = ROOT / "scripts" / "render-html-to-pdf.mjs"
    if script.exists():
        r = subprocess.run(
            ["node", str(script), str(html_path), str(pdf_path)],
            cwd=ROOT, capture_output=True, text=True,
        )
        if r.returncode == 0 and pdf_path.exists():
            return True
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        c = canvas.Canvas(str(pdf_path), pagesize=A4)
        w, h = A4
        c.setFont("STSong-Light", 10)
        y = h - 40
        title = payload.get("title", "操作日报")
        for line in [title, f"日期: {payload.get('trade_date','')}", f"模式: {payload.get('report_mode','')}"]:
            c.drawString(40, y, line[:80])
            y -= 18
        c.save()
        return pdf_path.exists()
    except Exception:
        return False


def deliver_trading_pdfs(trade_date: str, modes: dict[str, Any]) -> dict[str, str]:
    y, m, _ = trade_date.split("-")
    dest = DESKTOP_ROOT / y / m
    dest.mkdir(parents=True, exist_ok=True)
    delivered: dict[str, str] = {}
    for mode, info in modes.items():
        pdf = info.get("pdf")
        if pdf and Path(pdf).exists():
            name = Path(pdf).name
            dst = dest / name
            shutil.copy2(pdf, dst)
            delivered[f"{mode}_pdf"] = str(dst)
    return delivered
