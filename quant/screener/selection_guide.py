"""Enhanced stock-selection guide for beginner investors."""

from __future__ import annotations

from typing import Any


def build_selection_guide(
    *,
    preset: str,
    mode: str,
    capital_cny: float,
    price_min_cny: float,
    price_max_cny: float | None,
    enforce_capital_price_ceiling: bool,
    universe_size: int,
    candidate_count: int,
    validation_status: str,
    as_of_date: str | None,
) -> dict[str, Any]:
    eff_max = price_max_cny
    auto_ceiling = round(capital_cny / 100, 2) if capital_cny > 0 else None
    if enforce_capital_price_ceiling and auto_ceiling:
        eff_max = min(eff_max, auto_ceiling) if eff_max else auto_ceiling

    price_filter_text = []
    if price_min_cny > 0:
        price_filter_text.append(f"最低价 ≥ ¥{price_min_cny:.2f}")
    if eff_max:
        price_filter_text.append(f"最高价 ≤ ¥{eff_max:.2f}")
    if enforce_capital_price_ceiling and auto_ceiling:
        price_filter_text.append(f"按资金 ¥{capital_cny:,.0f} 自动限制（一手100股可负担）")

    return {
        "title": "增强版选股指南",
        "preset_label": {"balanced": "均衡", "momentum": "动量", "trend": "趋势", "low_vol": "低波动"}.get(preset, preset),
        "mode_label": "收盘数据（快速）" if mode == "eod" else "实时智能",
        "capital_cny": capital_cny,
        "price_min_cny": price_min_cny,
        "price_max_cny": price_max_cny,
        "effective_price_max_cny": eff_max,
        "enforce_capital_price_ceiling": enforce_capital_price_ceiling,
        "price_filter_summary": " · ".join(price_filter_text) if price_filter_text else "未设股价区间（全市场流动性筛选仍生效）",
        "steps": [
            f"1. 确认数据截至 {as_of_date or '最新收盘'}，模式：{'收盘因子' if mode == 'eod' else '实时+收盘混合'}。",
            f"2. 股价筛选：{price_filter_text[0] if price_filter_text else '无额外股价限制'}" +
            (f"{' · ' + price_filter_text[1] if len(price_filter_text) > 1 else ''}"),
            "3. 看「名称+代码+专业说明」列：名称来自本地证券主数据，说明来自多因子+Alpha158-lite 模型。",
            "4. 关注「可买/资格」：涨停附近、流动性不足、验证未通过会被标记 BLOCKED 或 WATCHLIST。",
            f"5. 按资金 ¥{capital_cny:,.0f} 查看「5000元」列建议手数；A股最少 100 股一手，T+1 当日买入不可卖。",
            "6. 先用「模拟练习」验证，再在券商页「实盘」预填——你必须在官方 App 亲自确认，系统不自动扣款。",
        ],
        "field_glossary": [
            {"term": "Rank IC", "plain": "模型排名与后续收益的相关程度，越高说明排序越有效（非收益保证）"},
            {"term": "Crash risk", "plain": "估算急跌风险，数值越高越应降低仓位"},
            {"term": "Model uncertainty", "plain": "模型分歧或样本不足程度，高时不建议实盘"},
            {"term": "Paper eligible", "plain": "适合模拟盘验证，不代表可实盘"},
            {"term": "Purged K-Fold", "plain": "剔除未来信息泄露的样本外验证方法（López de Prado）"},
        ],
        "universe_size": universe_size,
        "candidate_count": candidate_count,
        "validation_status": validation_status,
        "warnings": _warnings(validation_status, candidate_count, universe_size),
    }


def _warnings(validation_status: str, candidates: int, universe: int) -> list[str]:
    out: list[str] = []
    if validation_status in ("NOT_RUN", "NOT_READY", "BLOCKED_BY_DATA"):
        out.append("模型验证未完成或样本不足：结果仅供研究，默认禁止自动实盘。")
    if candidates == 0 and universe > 0:
        out.append("当前股价/流动性条件下无候选——尝试放宽最高价或降低最小成交额。")
    out.append("不构成投资建议；历史表现不代表未来。")
    return out


def resolve_price_filters(
    *,
    price_min_cny: float = 0.0,
    price_max_cny: float | None = None,
    capital_cny: float | None = None,
    enforce_capital_price_ceiling: bool = True,
) -> tuple[float, float | None, float | None, float]:
    """Return (pmin, user_pmax, effective_pmax, capital)."""
    cap = float(capital_cny or 5000.0)
    pmin = max(0.0, float(price_min_cny or 0))
    user_max = float(price_max_cny) if price_max_cny and price_max_cny > 0 else None
    eff_max = user_max
    if enforce_capital_price_ceiling and cap > 0:
        auto_max = round(cap / 100.0, 2)
        eff_max = min(eff_max, auto_max) if eff_max else auto_max
    return pmin, user_max, eff_max, cap


def price_passes(close: float, *, pmin: float, eff_max: float | None) -> bool:
    if pmin > 0 and close < pmin:
        return False
    if eff_max and close > eff_max:
        return False
    return True
