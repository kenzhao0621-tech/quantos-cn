"""Chinese daily report generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from tools.china_quant.freshness import DataStatus, FreshnessResult
from tools.china_quant.regime import RegimeResult
from tools.china_quant.rules import t_plus_one_note


@dataclass
class CandidatePlan:
    name: str
    code: str
    exchange: str
    sector: str
    price: float
    data_time: str
    recommendation: str  # 观察 / 可轻仓试探 / 暂不买入
    confidence: str
    score: float
    reasons: list[str]
    entry_range: str
    entry_confirm: str
    cancel_condition: str
    stop: str
    target1: str
    target2: str
    hold_period: str
    position_pct: str
    reward_risk: str
    catalyst: str
    risks: list[str]
    invalidation: str


@dataclass
class DailyReport:
    conclusion_direction: str
    market_regime_zh: str
    position_guidance: str
    trade_today: str
    data_cutoff: str
    data_status: str
    one_liner: str
    regime: RegimeResult
    freshness: FreshnessResult
    primary: list[CandidatePlan] = field(default_factory=list)
    watchlist: list[CandidatePlan] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)


def render_report(r: DailyReport) -> str:
    lines = [
        "# A股每日交易作战简报",
        "",
        "## 1. 今日结论",
        "",
        f"- 市场方向：{r.conclusion_direction}",
        f"- 市场状态：{r.market_regime_zh}",
        f"- 建议仓位：{r.position_guidance}",
        f"- 今日是否适合交易：{r.trade_today}",
        f"- 数据截止时间：{r.data_cutoff}",
        f"- 数据状态：{r.data_status}",
        f"- 一句话判断：{r.one_liner}",
        "",
        "## 2. 大盘分析",
        "",
        r.regime.guidance_zh,
        "",
        t_plus_one_note(),
        "",
    ]

    if r.primary:
        lines += ["## 4. 今日首选股票", ""]
        for i, c in enumerate(r.primary, 1):
            lines += _render_candidate(i, c)
    else:
        lines += [
            "## 4. 今日首选股票",
            "",
            "**今日无首选标的（NO TRADE / 观望为主）**",
            "",
        ]

    if r.watchlist:
        lines += ["## 5. 次级观察名单", ""]
        for c in r.watchlist:
            lines += [
                f"- **{c.name} ({c.code})**：{c.recommendation}",
                f"  - 观察理由：{'；'.join(c.reasons[:2])}",
                f"  - 触发条件：{c.entry_confirm}",
                f"  - 暂不买入：{c.cancel_condition}",
                "",
            ]

    if r.avoid:
        lines += ["## 6. 建议回避", ""]
        for a in r.avoid:
            lines.append(f"- {a}")
        lines.append("")

    lines += [
        "## 8. 风险提示",
        "",
        "- 本报告是基于概率的研究计划，不代表确定性结果。",
        "- 没有止损就不要进场。",
        "- 大幅高开后不要盲目追涨。",
        "- 不要使用生活必需资金。",
        "- 真实交易必须由您本人最终决定。",
        "- 本系统仅支持研究与模拟，不会自动下单。",
        "",
    ]
    return "\n".join(lines)


def _render_candidate(i: int, c: CandidatePlan) -> list[str]:
    return [
        f"### {i}. {c.name}（{c.code}）",
        "",
        f"- 当前价格：{c.price}",
        f"- 数据时间：{c.data_time}",
        f"- 所属板块：{c.sector}",
        f"- 建议：{c.recommendation}",
        f"- 置信度：{c.confidence}",
        f"- 综合评分：{c.score:.0f}",
        f"- 入选原因：{'；'.join(c.reasons)}",
        f"- 理想买入区间：{c.entry_range}",
        f"- 买入确认条件：{c.entry_confirm}",
        f"- 取消买入条件：{c.cancel_condition}",
        f"- 止损位：{c.stop}",
        f"- 第一止盈区间：{c.target1}",
        f"- 第二止盈区间：{c.target2}",
        f"- 建议持有周期：{c.hold_period}",
        f"- 建议仓位：{c.position_pct}",
        f"- 预期盈亏比：{c.reward_risk}",
        f"- 主要催化：{c.catalyst}",
        f"- 主要风险：{'；'.join(c.risks)}",
        f"- 什么情况说明判断错误：{c.invalidation}",
        "",
    ]
