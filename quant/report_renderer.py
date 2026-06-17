"""Daily report HTML/PDF rendering and Desktop delivery."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT / "docs" / "ai" / "daily-trading" / "daily"
DESKTOP_ROOT = Path("/Users/kenzhao/Desktop/China_A_Share_Daily_Reports")
WATERMARK = "PAPER_TRADING_ONLY — 仅供研究，非投资建议"


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_html(report: dict[str, Any]) -> str:
    d = report.get("data_cutoff") or report.get("target_trading_date") or datetime.now().strftime("%Y-%m-%d")
    decision = report.get("decision", "NO_TRADE")
    candidate = report.get("candidate") or {}
    sections = report.get("sections") or {}
    data_audit = sections.get("data_audit") or {}
    market_state = sections.get("market_state") or {}
    screening = sections.get("screening") or {}
    sectors = sections.get("sectors") or {}
    fundamentals = sections.get("fundamentals") or {}
    disc = (report.get("sections") or {}).get("disclosures") or {}
    disc_state = disc.get("disclosure_readiness", {}).get("state", "")
    top_watch = screening.get("top10_watch") or []
    evidence = market_state.get("evidence") or []
    rows = [
        f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>",
        "<title>China A-share Daily Quant Report</title>",
        "<style>",
        "body{font-family:'PingFang SC','Microsoft YaHei',sans-serif;margin:40px;color:#1a1a1a;}",
        "h1{font-size:22px;border-bottom:2px solid #333;padding-bottom:8px;}",
        "h2{font-size:16px;margin-top:24px;color:#333;}",
        ".meta{color:#555;font-size:13px;}",
        ".decision{font-size:18px;font-weight:bold;padding:12px;background:#f4f4f4;border-left:4px solid #0066cc;}",
        ".blocked{border-left-color:#cc0000;}",
        ".watermark{position:fixed;bottom:20px;right:20px;opacity:0.35;font-size:11px;}",
        "table{border-collapse:collapse;width:100%;font-size:12px;}",
        "td,th{border:1px solid #ccc;padding:6px;text-align:left;}",
        "@page{size:A4 portrait;margin:20mm;}",
        "</style></head><body>",
        f"<h1>中国A股量化交易日报</h1>",
        f"<p class='meta'>报告日期: {d} | Run ID: {report.get('run_id','')} | 数据截止: {report.get('data_cutoff','')}</p>",
        f"<p class='meta'>Provider: {report.get('provider','')} | Freshness: {report.get('freshness','')}</p>",
        f"<div class='decision {'blocked' if 'BLOCKED' in decision else ''}'>决策: {decision}</div>",
        f"<h2>市场状态</h2><p>Regime: {report.get('regime','')} ({report.get('regime_confidence','')}) | Score: {report.get('regime_score','')}</p>",
        f"<p>上涨: {market_state.get('advance','—')} | 下跌: {market_state.get('decline','—')}</p>",
        "<ul>" + "".join(f"<li>{x}</li>" for x in evidence[:8]) + "</ul>",
        f"<h2>数据审计</h2><p>Provider: {report.get('provider','')} | Freshness: {report.get('freshness','')} | Spot rows: {report.get('spot_row_count',0)}</p>",
        f"<p>Quality gate: {data_audit.get('quality_gate','—')} | Historical: {data_audit.get('historical',{})}</p>",
        f"<h2>候选池与筛选</h2><p>Initial universe: {screening.get('initial_universe','—')}</p>",
        "<p>Top watch: " + ", ".join(str(x) for x in top_watch[:10]) + "</p>",
        f"<h2>行业/基本面/公告覆盖</h2><p>Sectors: {sectors.get('status','—')} ({sectors.get('total_rows','—')} rows) | Fundamentals: {fundamentals.get('status','—')}</p>",
        f"<p>Disclosure state: {disc_state} | Rows: {disc.get('total_rows',0)} | Verified zero: {disc.get('verified_zero_results',False)}</p>",
    ]
    if candidate:
        rows += [
            "<h2>候选标的</h2><table><tr><th>代码</th><th>名称</th><th>得分</th><th>入场区</th><th>止损</th><th>目标1</th></tr>",
            f"<tr><td>{candidate.get('code','')}</td><td>{candidate.get('name','')}</td>"
            f"<td>{candidate.get('total_score','')}</td><td>{candidate.get('preferred_entry_zone','')}</td>"
            f"<td>{candidate.get('paper_stop','')}</td><td>{candidate.get('target_1','')}</td></tr></table>",
            "<p>T+1 规则适用。必须等待入场触发，不追高，不满仓。</p>",
        ]
    else:
        rows.append("<h2>NO_TRADE / 阻塞原因</h2><ul>")
        for r in report.get("no_trade_reasons", []):
            rows.append(f"<li>{r}</li>")
        rows.append("</ul>")
    rows += [
        "<h2>次交易日行动清单</h2>",
        "<ol><li>开盘前检查实时数据 freshness 与涨跌停状态。</li><li>仅在候选仍满足板块/流动性/趋势条件时进入 Paper/Shadow。</li><li>若高开回落或跌破入场区，取消计划。</li><li>收盘后做 T+1 验证并记录失败原因。</li></ol>",
        "<h2>风险与限制</h2><p>本报告不构成投资建议。真实资金交易必须由用户本人在官方券商平台确认。</p>",
        f"<div class='watermark'>{WATERMARK}</div>",
        "</body></html>",
    ]
    return "".join(rows)


def render_action_sheet_html(report: dict[str, Any]) -> str:
    d = report.get("target_trading_date") or report.get("data_cutoff", "")
    decision = report.get("decision", "NO_TRADE")
    c = report.get("candidate") or {}
    blocked = "BLOCKED" in decision
    lines = [
        f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'><title>次交易日操作清单</title>",
        "<style>body{font-family:'PingFang SC',sans-serif;margin:30px;} h1{font-size:20px;}",
        ".warn{background:#fff3cd;padding:10px;border:1px solid #ffc107;}</style></head><body>",
        f"<h1>次交易日操作清单 — {d}</h1>",
        f"<p><strong>决策:</strong> {decision}</p>",
    ]
    if blocked or not c:
        lines.append(f"<div class='warn'><strong>阻塞:</strong> {'; '.join(report.get('no_trade_reasons', [])) or decision}</div>")
        lines.append("<p>请勿臆造价格。等待数据就绪。</p>")
    else:
        lines += [
            f"<p>候选: {c.get('code')} {c.get('name')}</p>",
            f"<p>入场区: {c.get('preferred_entry_zone')} | 最高可接受: {c.get('maximum_acceptable_entry')}</p>",
            f"<p>勿追价: {c.get('do_not_chase_level')} | 止损: {c.get('paper_stop')}</p>",
            f"<p>目标1: {c.get('target_1')} | 目标2: {c.get('target_2')}</p>",
            "<p><strong>T+1 警告:</strong> 当日买入不可当日卖出。</p>",
        ]
    lines.append("</body></html>")
    return "".join(lines)


def _render_pdf_playwright(html_path: Path, pdf_path: Path) -> bool:
    script = ROOT / "scripts" / "render-html-to-pdf.mjs"
    if not script.exists():
        return False
    r = subprocess.run(
        ["node", str(script), str(html_path), str(pdf_path)],
        cwd=ROOT, capture_output=True, text=True,
    )
    return r.returncode == 0 and pdf_path.exists()


def _render_pdf_reportlab(html_content: str, pdf_path: Path, report: dict[str, Any]) -> bool:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except ImportError:
        return False
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    w, h = A4
    c.setFont("STSong-Light", 10)
    y = h - 40
    c.drawString(40, y, f"China A-share Daily Report — {report.get('data_cutoff','')}")
    y -= 20
    c.drawString(40, y, f"Decision: {report.get('decision','')}")
    y -= 20
    c.drawString(40, y, f"Run ID: {report.get('run_id','')}")
    y -= 20
    c.drawString(40, y, WATERMARK[:60])
    y -= 30
    for line in (report.get("no_trade_reasons") or [])[:8]:
        c.drawString(40, y, str(line)[:80])
        y -= 16
        if y < 60:
            c.showPage()
            c.setFont("STSong-Light", 10)
            y = h - 40
    c.save()
    return pdf_path.exists()


def qa_pdf(pdf_path: Path, report: dict[str, Any], *, min_bytes: int = 800) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    exists = pdf_path.exists()
    checks.append({"name": "pdf_exists", "passed": exists})
    size = pdf_path.stat().st_size if exists else 0
    checks.append({"name": "min_size", "passed": size >= min_bytes, "detail": str(size)})
    content_hash = _hash_file(pdf_path) if exists else ""
    checks.append({"name": "hash_recorded", "passed": bool(content_hash), "hash": content_hash})
    passed = all(c["passed"] for c in checks)
    return {"passed": passed, "checks": checks, "file_size": size, "sha256": content_hash}


def deliver_to_desktop(
    *,
    report_json: Path,
    report_md: Path,
    report_html: Optional[Path] = None,
    report_pdf: Optional[Path] = None,
    action_pdf: Optional[Path] = None,
) -> dict[str, Any]:
    data = json.loads(report_json.read_text(encoding="utf-8"))
    d = data.get("data_cutoff") or datetime.now().strftime("%Y-%m-%d")
    y, m, _ = d.split("-")
    dest = DESKTOP_ROOT / y / m
    dest.mkdir(parents=True, exist_ok=True)
    delivered: dict[str, str] = {}

    def _copy(src: Path, name: str) -> None:
        dst = dest / name
        if dst.exists() and _hash_file(dst) != _hash_file(src):
            ver = datetime.now().strftime("%H%M%S")
            dst = dest / name.replace(".", f"_{ver}.")
        shutil.copy2(src, dst)
        delivered[name] = str(dst)

    _copy(report_json, f"{d}_量化交易日报.json")
    _copy(report_md, f"{d}_量化交易日报.md")
    if report_html and report_html.exists():
        _copy(report_html, f"{d}_量化交易日报.html")
    if report_pdf and report_pdf.exists():
        _copy(report_pdf, f"{d}_量化交易日报.pdf")
    if action_pdf and action_pdf.exists():
        _copy(action_pdf, f"{d}_次交易日操作清单.pdf")
    return {"desktop_dir": str(dest), "delivered": delivered}


def render_all_formats(report_dict: dict[str, Any], *, base_name: Optional[str] = None) -> dict[str, Any]:
    d = report_dict.get("data_cutoff") or datetime.now().strftime("%Y-%m-%d")
    base = base_name or f"{d}_DAILY_QUANT_REPORT"
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    jp = DAILY_DIR / f"{base}.json"
    mp = DAILY_DIR / f"{base}.md"
    hp = DAILY_DIR / f"{base}.html"
    pp = DAILY_DIR / f"{base}.pdf"
    asp = DAILY_DIR / f"{d}_NEXT_SESSION_ACTION_SHEET.pdf"

    report_dict["generated_at"] = datetime.now().isoformat(timespec="seconds")
    jp.write_text(json.dumps(report_dict, ensure_ascii=False, indent=2), encoding="utf-8")

    html = render_html(report_dict)
    hp.write_text(html, encoding="utf-8")

    md_lines = [
        f"# 中国A股量化交易日报 — {d}",
        "",
        f"**Decision:** `{report_dict.get('decision')}`",
        f"**Run ID:** `{report_dict.get('run_id')}`",
        f"**Provider:** `{report_dict.get('provider')}`",
        f"**Freshness:** `{report_dict.get('freshness')}`",
        f"**Rows:** `{report_dict.get('spot_row_count')}`",
        "",
        "## 市场状态",
        f"- Regime: `{report_dict.get('regime')}`",
        f"- Confidence: `{report_dict.get('regime_confidence')}`",
        f"- Score: `{report_dict.get('regime_score')}`",
        "",
    ]
    sections = report_dict.get("sections") or {}
    market_state = sections.get("market_state") or {}
    for ev in (market_state.get("evidence") or [])[:8]:
        md_lines.append(f"- {ev}")
    candidate = report_dict.get("candidate") or {}
    if candidate:
        md_lines += [
            "",
            "## 候选标的",
            f"- 代码: `{candidate.get('code')}`",
            f"- 名称: `{candidate.get('name')}`",
            f"- 得分: `{candidate.get('total_score')}`",
            f"- 入场区: `{candidate.get('preferred_entry_zone')}`",
            f"- 止损: `{candidate.get('paper_stop')}`",
            f"- 目标: `{candidate.get('target_1')}` / `{candidate.get('target_2')}`",
            f"- 取消条件: {', '.join(candidate.get('cancel_conditions') or [])}",
        ]
    else:
        md_lines += ["", "## 不交易/阻塞原因"]
        md_lines += [f"- {x}" for x in report_dict.get("no_trade_reasons", [])]
    screening = sections.get("screening") or {}
    md_lines += [
        "",
        "## 候选池与数据审计",
        f"- 初始样本: `{screening.get('initial_universe', '—')}`",
        f"- Top watch: `{', '.join(str(x) for x in (screening.get('top10_watch') or [])[:10])}`",
        "",
        "## 次交易日行动清单",
        "1. 开盘前检查实时数据 freshness 与涨跌停状态。",
        "2. 仅在候选仍满足板块/流动性/趋势条件时进入 Paper/Shadow。",
        "3. 若高开回落或跌破入场区，取消计划。",
        "4. 收盘后做 T+1 验证并记录失败原因。",
        "",
        "## 风险声明",
        "本报告不构成投资建议。真实资金交易必须由用户本人在官方券商平台确认。",
    ]
    mp.write_text("\n".join(md_lines), encoding="utf-8")

    pdf_ok = _render_pdf_playwright(hp, pp)
    if not pdf_ok:
        pdf_ok = _render_pdf_reportlab(html, pp, report_dict)

    action_html = DAILY_DIR / f"{d}_NEXT_SESSION_ACTION_SHEET.html"
    action_html.write_text(render_action_sheet_html(report_dict), encoding="utf-8")
    action_pdf_ok = _render_pdf_playwright(action_html, asp)
    if not action_pdf_ok:
        action_pdf_ok = _render_pdf_reportlab(action_html.read_text(), asp, report_dict)

    qa = qa_pdf(pp, report_dict) if pdf_ok else {"passed": False, "checks": [{"name": "render_failed", "passed": False}]}
    delivery = {}
    if qa.get("passed"):
        delivery = deliver_to_desktop(
            report_json=jp, report_md=mp, report_html=hp, report_pdf=pp,
            action_pdf=asp if action_pdf_ok else None,
        )
        report_dict["desktop_delivery"] = delivery
        jp.write_text(json.dumps(report_dict, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "json": str(jp), "md": str(mp), "html": str(hp), "pdf": str(pp) if pdf_ok else "",
        "action_sheet_pdf": str(asp) if action_pdf_ok else "",
        "pdf_qa": qa, "desktop_delivery": delivery,
    }
