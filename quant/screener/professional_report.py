"""Institutional-style stock selection narrative for beginners and pros."""

from __future__ import annotations

from typing import Any


def build_professional_report(
    *,
    symbol: str,
    name: str,
    rank: int,
    score: float,
    sector: str,
    factor_breakdown: list[dict[str, Any]],
    detailed_reasons: list[str],
    trade_zones: dict[str, Any],
    data_tier: str,
    as_of_date: str,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    display = f"{name}（{symbol}）" if name else symbol
    top_factors = sorted(factor_breakdown, key=lambda x: abs(float(x.get("contribution") or 0)), reverse=True)[:4]
    factor_narrative = "；".join(
        f"{f.get('factor')}贡献{f.get('contribution', 0):+.2f}（z={f.get('z_score', 0):+.2f}）"
        for f in top_factors
    ) or "多因子综合靠前，无单一极端因子主导"

    thesis = (
        f"【标的】{display} · 板块 {sector or '未分类'}\n"
        f"【排名】第 {rank} 名 · 综合分 {score:.3f} · 数据截至 {as_of_date or '—'}（{data_tier}）\n"
        f"【核心逻辑】{factor_narrative}。\n"
        f"【基本面佐证】{'；'.join(detailed_reasons[:4]) if detailed_reasons else '流动性与趋势通过截面筛选'}。"
    )

    if trade_zones:
        thesis += (
            f"\n【交易区间（研究参考）】买入 ¥{trade_zones.get('buy_zone_low')}–¥{trade_zones.get('buy_zone_high')}；"
            f"止盈 ¥{trade_zones.get('sell_zone_low')}–¥{trade_zones.get('sell_zone_high')}；"
            f"止损约 ¥{trade_zones.get('stop_loss')}。"
        )

    val_note = ""
    if validation:
        if validation.get("passed"):
            val_note = (
                f"Purged K-Fold 样本外验证通过：{validation.get('folds')} 折 "
                f"平均收益 {validation.get('mean_oos_return_pct')}% · 命中率 {validation.get('mean_hit_rate', 0)*100:.0f}%。"
            )
        else:
            val_note = "当前预设的样本外验证未完全达标，建议降低仓位或延长 Paper 观察期。"

    sections = [
        {"title": "投资论点", "body": thesis},
        {"title": "因子拆解", "body": factor_narrative, "items": top_factors},
        {"title": "风险边界", "body": "；".join([
            "量化排名不等于未来收益",
            "T+1 制度下当日买入不可卖出",
            "涨跌停/停牌可能导致无法成交",
            trade_zones.get("disclaimer", "") if trade_zones else "",
        ])},
    ]
    if val_note:
        sections.append({"title": "样本外验证", "body": val_note})

    return {
        "headline": f"{display} — 多因子候选第 {rank} 名",
        "thesis": thesis,
        "sections": sections,
        "disclaimer": "本报告由系统根据历史行情与因子模型自动生成，不构成投资建议。",
    }
