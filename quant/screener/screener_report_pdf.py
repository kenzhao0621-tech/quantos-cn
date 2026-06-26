"""Human-readable PDF export for screener symbol analysis."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from gateway.config import ROOT

REPORT_DIR = ROOT / "docs" / "ai" / "daily-trading" / "screener_reports"
WATERMARK = "PAPER_TRADING_ONLY — 仅供研究，非投资建议"


def _render_html(dossier: dict[str, Any], *, symbol: str) -> str:
    name = dossier.get("name") or symbol
    zones = dossier.get("trade_zones") or {}
    score = dossier.get("score") or dossier.get("final_score") or "—"
    plain = dossier.get("plain_language") or ""
    reasons = dossier.get("detailed_reasons") or []
    pos = dossier.get("positive_factors") or []
    neg = dossier.get("negative_factors") or []
    invalid = dossier.get("invalidation_conditions") or []
    not_trade = dossier.get("reasons_not_to_trade") or []
    as_of = dossier.get("as_of_date") or dossier.get("data_cutoff") or datetime.now().strftime("%Y-%m-%d")

    def li(items: list) -> str:
        return "<ul>" + "".join(f"<li>{x}</li>" for x in items[:12]) + "</ul>" if items else "<p>—</p>"

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<title>{name} 选股分析报告</title>
<style>
body{{font-family:'PingFang SC','Microsoft YaHei',sans-serif;margin:36px;color:#1a1a1a;line-height:1.5;}}
h1{{font-size:20px;border-bottom:2px solid #333;padding-bottom:8px;}}
h2{{font-size:15px;margin-top:20px;color:#333;}}
.meta{{color:#555;font-size:12px;}}
.score{{font-size:28px;font-weight:bold;color:#0066cc;}}
table{{border-collapse:collapse;width:100%;font-size:12px;margin-top:8px;}}
td,th{{border:1px solid #ccc;padding:6px;text-align:left;}}
.warn{{color:#b45309;}}
.watermark{{position:fixed;bottom:16px;right:16px;opacity:0.35;font-size:10px;}}
@page{{size:A4 portrait;margin:18mm;}}
</style></head><body>
<h1>{name}（{symbol}）选股分析报告</h1>
<p class="meta">数据截止: {as_of} | 模型: {dossier.get('model_version','')} | 生成: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<p class="score">综合得分: {score}</p>
<h2>一句话解读</h2><p>{plain or '—'}</p>
<h2>买卖区间参考（非盈利承诺）</h2>
<table><tr><th>类型</th><th>区间/价格</th></tr>
<tr><td>建议买入</td><td>¥{zones.get('buy_zone_low','—')} – ¥{zones.get('buy_zone_high','—')}</td></tr>
<tr><td>止损参考</td><td>¥{zones.get('stop_loss','—')}</td></tr>
<tr><td>止盈参考</td><td>¥{zones.get('sell_zone_low','—')} – ¥{zones.get('sell_zone_high','—')}</td></tr>
</table>
{'<p class="warn">接近涨停，不建议追入。</p>' if zones.get('chase_warning') else ''}
<h2>专业因子说明</h2>{li(reasons)}
<h2>多空因子</h2><p><b>利多</b></p>{li(pos)}<p><b>利空</b></p>{li(neg)}
<h2>失效条件</h2><p>{'；'.join(invalid) if invalid else '—'}</p>
<h2>不宜交易</h2><p>{'；'.join(not_trade) if not_trade else '—'}</p>
<h2>风险声明</h2><p>本报告由 QuantOS 量化模型自动生成，不构成投资建议。真实交易须在券商官方平台由本人确认。</p>
<div class="watermark">{WATERMARK}</div>
</body></html>"""


def render_screener_analysis_pdf(dossier: dict[str, Any], *, symbol: str) -> dict[str, Any]:
    """Render dossier to HTML + PDF; returns paths and download hint."""
    from quant.report_renderer import _render_pdf_playwright, _render_pdf_reportlab

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_sym = symbol.replace(".", "_")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = REPORT_DIR / f"{safe_sym}_{stamp}"
    html_path = base.with_suffix(".html")
    pdf_path = base.with_suffix(".pdf")
    json_path = base.with_suffix(".json")

    html = _render_html(dossier, symbol=symbol)
    html_path.write_text(html, encoding="utf-8")
    json_path.write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")

    pdf_ok = _render_pdf_playwright(html_path, pdf_path)
    if not pdf_ok:
        pdf_ok = _render_pdf_reportlab(html, pdf_path, dossier)

    return {
        "symbol": symbol,
        "html": str(html_path),
        "pdf": str(pdf_path) if pdf_ok else "",
        "json": str(json_path),
        "pdf_ready": pdf_ok,
        "download_file": pdf_path.name if pdf_ok else "",
        "download_url": f"/api/v1/screener/report/download?file={pdf_path.name}" if pdf_ok else "",
    }
