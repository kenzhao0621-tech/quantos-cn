"""Four-panel advice card (v2.2 §8.1-8.2).

A. verified facts (with source_url + updated_at)
B. quantitative computation (formula/weight version + data time)
C. model prediction (explicitly labelled 不保证发生)
D. conditional advice (buy zone / stop / targets / position — condition-triggered)

The card also carries the §8.2 headline block: conclusion, top reasons, top
risks, data freshness, formula version, cache status, updated time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from quant.explain_os.language_guard import scrub_payload
from quant.explain_os.score_breakdown import build_score_breakdown

RECOMMENDATION_LABELS_ZH = {
    "buy_zone": "轻仓买入（仅限计划区间）",
    "watch": "观察",
    "wait_pullback": "等待回调",
    "avoid": "不建议买入",
    "hold": "持有",
    "sell": "卖出",
    "insufficient_structure": "结构数据不足，暂不建议",
}

PREDICTION_DISCLAIMER = "模型预测仅供参考，不保证发生；预测不构成买卖依据的全部。"
GLOBAL_DISCLAIMER = "本内容为量化研究与模拟交易辅助，不构成投资建议，不承诺任何收益。"


def build_advice_card(
    *,
    symbol: str,
    name: str,
    score_result: Dict[str, Any],
    trade_plan: Dict[str, Any],
    confidence: Dict[str, Any],
    facts: List[Dict[str, Any]],
    predictions: Optional[List[Dict[str, Any]]] = None,
    cache_provenance: Optional[List[Dict[str, Any]]] = None,
    data_freshness_label: str = "",
    generated_at: str = "",
) -> Dict[str, Any]:
    """Assemble the full explanation card. Every fact must carry source_url and
    updated_at — facts without provenance are moved to an "unverified" bucket
    and never presented as verified."""
    predictions = predictions or []
    cache_provenance = cache_provenance or []
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    verified_facts, unverified = [], []
    for f in facts:
        if f.get("source_url") and f.get("updated_at"):
            verified_facts.append(f)
        else:
            unverified.append(dict(f, provenance_missing=True))

    breakdown = build_score_breakdown(score_result)

    hard_blocked = bool(score_result.get("hard_blocked"))
    recommendation = "avoid" if hard_blocked else str(trade_plan.get("recommendation", "watch"))
    if not hard_blocked and not confidence.get("actionable", False) and recommendation == "buy_zone":
        recommendation = "watch"  # low confidence downgrades to watch (§6.6)

    top_reasons = _top_reasons(breakdown)
    top_risks = _top_risks(score_result, trade_plan)

    labelled_predictions = [
        dict(p, disclaimer=PREDICTION_DISCLAIMER, is_forecast=True) for p in predictions
    ]

    cache_statuses = [c.get("cache_status", "") for c in cache_provenance]
    overall_cache = "force_refresh" if "force_refresh" in cache_statuses else (
        "cache_miss" if "miss" in cache_statuses else ("cache_hit" if cache_statuses else "no_cache_info"))

    card = {
        "symbol": symbol,
        "name": name,
        "generated_at": generated_at,
        "headline": {
            "conclusion": RECOMMENDATION_LABELS_ZH.get(recommendation, recommendation),
            "recommendation": recommendation,
            "top_reasons": top_reasons[:3],
            "top_risks": top_risks[:3],
            "data_freshness": data_freshness_label or "未知",
            "score_weight_version": score_result.get("score_weight_version"),
            "cache_status": overall_cache,
            "updated_at": generated_at,
            "confidence": confidence.get("confidence"),
            "confidence_band": confidence.get("band_label_zh"),
        },
        "panel_a_verified_facts": verified_facts,
        "panel_a_unverified": unverified,
        "panel_b_quant_computation": breakdown,
        "panel_c_model_predictions": labelled_predictions,
        "panel_d_conditional_advice": {
            "trade_plan": trade_plan,
            "condition_note": "以上区间/价格均为条件触发计划，不是无条件买入指令。",
            "do_not_buy_conditions": trade_plan.get("do_not_buy_conditions") or [],
            "hard_blocked": hard_blocked,
            "hard_block_reasons": score_result.get("hard_block_reasons", []),
        },
        "cache_provenance": cache_provenance,
        "disclaimer": GLOBAL_DISCLAIMER,
    }
    cleaned, violations = scrub_payload(card)
    if violations:
        cleaned["language_guard_violations"] = violations
    return cleaned


def _top_reasons(breakdown: Dict[str, Any]) -> List[str]:
    rows = [r for r in breakdown.get("factors", []) if not r.get("missing")]
    rows.sort(key=lambda r: r.get("contribution", 0), reverse=True)
    out = []
    for r in rows[:3]:
        if r.get("score", 0) >= 55:
            out.append(f"{r['label_zh']}得分 {r['score']:.0f}（贡献 +{r['contribution']:.1f}，来源 {r.get('source') or '未标注'}）")
    return out or ["无显著正向因子 — 综合评分主要由中性因素构成"]


def _top_risks(score_result: Dict[str, Any], trade_plan: Dict[str, Any]) -> List[str]:
    risks: List[str] = list(score_result.get("hard_block_reasons", []))
    for penalty_key, label in (("risk_penalty", "风险惩罚"), ("overheat_penalty", "过热惩罚"),
                               ("execution_penalty", "执行惩罚")):
        p = score_result.get(penalty_key) or {}
        comps = [c for c in p.get("components", []) if (c.get("points") or 0) > 1.0]
        comps.sort(key=lambda c: c["points"], reverse=True)
        for c in comps[:1]:
            risks.append(f"{label}：{c['component']} 扣 {c['points']:.1f} 分")
    for m in score_result.get("missing_factors", []):
        risks.append(f"数据缺失：{m} 因子不可用，已降权处理")
    if trade_plan.get("minimum_lot_warning"):
        risks.append(trade_plan["minimum_lot_warning"])
    return risks or ["未识别出显著风险项（不代表无风险）"]
