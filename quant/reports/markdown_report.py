"""ReportOS Markdown generator — assembles real artifacts, labels degraded parts.

Every section states its data source and generation time. Missing artifacts are
reported as absent (NOT_RUN) — never filled with invented numbers.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DISCLAIMER = (
    "> **免责声明**：本报告为自动化研究输出，全部指标来自本地真实数据回测与模型推理，"
    "经过历史样本验证的结论也不代表未来收益。本系统仅供研究与辅助决策，"
    "**不构成投资建议**；默认仅支持模拟交易（paper trading），不支持真实券商自动下单。"
)


def _latest(pattern: str, base: Path) -> dict[str, Any] | None:
    files = sorted(base.glob(pattern))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _fmt_pct(v: Any) -> str:
    return f"{v}%" if isinstance(v, (int, float)) else "—"


def generate_research_report(*, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or ROOT / "artifacts" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    lines: list[str] = [
        "# QuantOS 2.0 研究日报",
        "",
        f"生成时间：{now.isoformat(timespec='seconds')} · 引擎：QuantOS × Kronos × TradingAgents-CN 风格",
        "",
        DISCLAIMER,
        "",
    ]
    degraded_sections: list[str] = []

    # 1. Data quality
    dq = _latest("data_quality_*.json", ROOT / "artifacts" / "reports")
    lines.append("## 1. 数据质量")
    if dq:
        cov = dq.get("view_coverage", {})
        db = cov.get("daily_bars", {})
        lines += [
            f"- 结论：**{dq.get('verdict')}**（{dq.get('generated_at')}）",
            f"- 日线：{db.get('rows')} 行，窗口 {db.get('min')} ~ {db.get('max')}（{db.get('distinct')} 个交易日）",
        ]
        if dq.get("degraded_views"):
            lines.append(f"- ⚠️ degraded 视图：{dq['degraded_views']}")
            degraded_sections.append("data_quality")
    else:
        lines.append("- 状态：NOT_RUN（请运行 `python scripts/check_data_quality.py --mode quick`）")
        degraded_sections.append("data_quality:not_run")
    lines.append("")

    # 2. Kronos
    kr = _latest("kronos_smoke_*.json", ROOT / "artifacts" / "reports")
    lines.append("## 2. Kronos 金融时序模型")
    if kr:
        p = kr.get("prediction", {})
        deg = p.get("degraded")
        lines += [
            f"- 模型：{p.get('model')}（{'**degraded — ' + str(p.get('reason')) + '**' if deg else '真实推理'}）",
            f"- 最近冒烟：{kr.get('generated_at')}，{p.get('symbol')} {p.get('horizon')} 日预期收益 "
            f"{round((p.get('expected_return') or 0) * 100, 2)}%，置信 {p.get('confidence')}",
        ]
        if deg:
            degraded_sections.append("kronos")
    else:
        lines.append("- 状态：NOT_RUN（请运行 `python scripts/run_kronos_smoke.py`）")
        degraded_sections.append("kronos:not_run")
    lines.append("")

    # 3. Backtest
    bt = _latest("backtest_*.json", ROOT / "artifacts" / "backtests")
    lines.append("## 3. 组合回测（扣成本/滑点，真实基准）")
    if bt:
        m = bt.get("metrics", {})
        gate = bt.get("validation_gate", {})
        win = bt.get("window", {})
        bench = (bt.get("benchmarks") or {}).get("benchmarks") or (bt.get("benchmarks") or {}).get("values") or {}
        lines += [
            f"- 真实窗口：{win.get('start')} ~ {win.get('end')}（{win.get('days')} 个信号日）",
            f"- 夏普 {m.get('sharpe')} · 累计净收益 {_fmt_pct(m.get('total_return_pct'))} · 最大回撤 {_fmt_pct(m.get('max_drawdown_pct'))} · 胜率 {_fmt_pct(m.get('win_rate_pct'))}",
            f"- 基准对比：沪深300 {_fmt_pct(bench.get('hs300_buy_hold'))} / 全市场等权 {_fmt_pct(bench.get('equal_weight_market'))}",
            f"- 验证门：**{gate.get('verdict')}**",
        ]
        for r in gate.get("reasons", []):
            lines.append(f"  - {r}")
    else:
        lines.append("- 状态：NOT_RUN（请运行 `python scripts/run_backtest.py --mode quick`）")
        degraded_sections.append("backtest:not_run")
    lines.append("")

    # 4. Research
    rs = _latest("research_*.json", ROOT / "artifacts" / "research")
    lines.append("## 4. 参数搜索与基线对比")
    if rs:
        s = rs.get("search", {})
        best = s.get("best_eligible") or s.get("best")
        lines += [
            f"- 面板窗口：{rs.get('panel_window', {}).get('start')} ~ {rs.get('panel_window', {}).get('end')}",
            f"- 通过验证门 {s.get('eligible_count')} 组 / 被拦截 {s.get('blocked_count')} 组（拦截结果如实保留）",
        ]
        if best:
            lines.append(f"- 最优{'（通过门）' if s.get('best_eligible') else '（未通过门）'}：`{best.get('params')}` 夏普 {best.get('metrics', {}).get('risk', {}).get('sharpe')}")
        pbo = s.get("pbo_real_variants")
        if pbo:
            lines.append(f"- 过拟合概率 PBO（真实参数变体）：{pbo.get('pbo')}")
        baselines = rs.get("baselines", {})
        rows = []
        for name, m in baselines.items():
            if m.get("status") == "OK":
                rows.append(f"| {name} | {m['risk']['sharpe']} | {m['return']['annualized_return_pct']}% | {m['risk']['max_drawdown_pct']}% |")
        if rows:
            lines += ["", "| 基线 | 夏普 | 年化收益 | 最大回撤 |", "|---|---|---|---|", *rows]
    else:
        lines.append("- 状态：NOT_RUN（请运行 `python scripts/run_research.py --mode quick --trials 30`）")
        degraded_sections.append("research:not_run")
    lines.append("")

    # 5. Agents
    ag_dir = ROOT / "artifacts" / "agents"
    ag = _latest("agents_*.json", ag_dir) if ag_dir.exists() else None
    lines.append("## 5. 多智能体研究结论")
    if ag:
        f = ag.get("final", {})
        lines += [
            f"- {ag.get('symbol')}（{ag.get('as_of_date')}）：评级 **{f.get('rating')}** — {f.get('rating_meaning')}",
            f"- 综合 {f.get('score')} · 置信 {f.get('confidence')}",
        ]
        if f.get("degraded_agents"):
            lines.append(f"- ⚠️ degraded 智能体：{f['degraded_agents']}")
            degraded_sections.append("agents")
        for c in (f.get("invalidation_conditions") or [])[:3]:
            lines.append(f"  - 失效条件：{c}")
    else:
        lines.append("- 状态：NOT_RUN（请运行 `python scripts/run_agents_analysis.py --symbol 000001.SZ`）")
        degraded_sections.append("agents:not_run")
    lines.append("")

    # 6. Degraded summary — mandated by the refactor prompt.
    lines.append("## 6. 真实性与降级状态汇总")
    if degraded_sections:
        lines.append(f"- 本报告存在 degraded/缺失 部分：`{degraded_sections}` — 相关结论不可作为决策依据。")
    else:
        lines.append("- 本报告所有部分均为真实运行输出，无降级。")
    lines += ["", DISCLAIMER, ""]

    path = out_dir / f"quantos_research_report_{now.strftime('%Y%m%d_%H%M%S')}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
