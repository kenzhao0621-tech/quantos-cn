"""Plain-language operation guides for new investors."""

from __future__ import annotations

from typing import Any


def build_beginner_guide(
    *,
    symbol: str,
    name: str,
    price: float,
    qty: int,
    notional: float,
    zones: dict[str, Any],
    reasons: list[str],
    data_as_of: str,
    data_tier: str,
    broker_handoff: str,
) -> dict[str, Any]:
    display = f"{name}（{symbol}）" if name else symbol
    steps = [
        f"1. 确认数据：当前参考价 ¥{price:.2f}，数据截至 {data_as_of or '未知'}，等级 {data_tier or 'EOD'}。延迟数据不能当作实时下单依据。",
        f"2. 看买入区间：建议在 ¥{zones.get('buy_zone_low', price):.2f} – ¥{zones.get('buy_zone_high', price):.2f} 之间分批挂单，避免追高。",
        f"3. 算仓位：按你的资金，系统建议买 {qty} 股（约 ¥{notional:.0f}），A股最少 100 股一手。",
        f"4. 设止损：若跌破约 ¥{zones.get('stop_loss', 0):.2f}，应退出或减仓（模拟盘先验证）。",
        f"5. 止盈参考：¥{zones.get('sell_zone_low', 0):.2f} – ¥{zones.get('sell_zone_high', 0):.2f} 区间可考虑分批卖出（T+1：买入当日不能卖）。",
        f"6. 模拟验证：先在「Paper」页启动模拟，把 {display} 加入模拟组合观察 3–5 个交易日。",
        f"7. 真实交易：{broker_handoff}。本系统不自动扣款，你必须在券商官方 App/客户端亲自确认。",
    ]
    if zones.get("chase_warning"):
        steps.insert(2, "⚠️ 该股接近涨停或波动剧烈，新手不建议当日追入。")

    summary = (
        f"{display} 进入候选前列，主要因为：{'；'.join(reasons[:4])}。"
        " 以下为操作参考，不构成投资建议。"
    )
    return {
        "summary": summary,
        "steps": steps,
        "why_selected": reasons,
        "cautions": [
            "量化模型可能失效，历史表现不代表未来",
            "A股 T+1：今天买的股票明天才能卖",
            "ST、停牌、涨跌停可能导致无法成交",
        ],
    }


def build_detailed_reasons(row: dict[str, Any], factor_breakdown: list[dict[str, Any]]) -> list[str]:
    """Expand factor hits into readable bullets."""
    out: list[str] = []
    for f in factor_breakdown[:6]:
        label = f.get("factor") or f.get("name") or "因子"
        contrib = f.get("contribution")
        z = f.get("z_score")
        if contrib is not None:
            out.append(f"{label}：截面排名靠前（贡献 {contrib:+.3f}，z={z:+.2f}）" if z is not None else f"{label}：贡献 {contrib:+.3f}")
    if row.get("ret_20", 0) > 5:
        out.append(f"近 20 日涨幅 {row['ret_20']:.1f}%，动量较强（也意味着回撤风险）")
    if row.get("avg_amount", 0) > 5e7:
        out.append(f"日均成交额约 {row['avg_amount']/1e8:.1f} 亿，流动性较好")
    if row.get("pe") and 0 < row["pe"] < 40:
        out.append(f"市盈率 PE≈{row['pe']:.1f}，估值在可接受范围")
    if row.get("dividend_yield") and row["dividend_yield"] > 1:
        out.append(f"股息率约 {row['dividend_yield']:.2f}%")
    return out[:8]
