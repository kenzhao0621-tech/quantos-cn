"""Multi-target enrichment for screener recommendation cards."""

from __future__ import annotations

import statistics
from typing import Any

from quant.portfolio.cost_model import estimate_round_trip_cost_cny
from quant.portfolio.allocator import affordable_lots
from quant.tradability.mask import evaluate_tradability

MODEL_VERSION = "screener_v2_multi_target_2026-06-17"
FORECAST_HORIZON = "T+1_close_to_close"


def enrich_candidate(
    row: dict[str, Any],
    *,
    rank: int,
    preset: str,
    as_of_date: str,
    capital_cny: float = 5000.0,
    validation_status: dict[str, Any] | None = None,
    regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add return/risk/uncertainty/cost channels to a screener row."""
    sym = row["symbol"]
    last_close = float(row.get("last_close") or 0)
    last_pct = float(row.get("last_pct") or 0)
    vol = float(row.get("vol_20") or 0)
    avg_amt = float(row.get("avg_amount") or 0)
    score = float(row.get("score") or 0)

    mask = evaluate_tradability(
        symbol=sym,
        last_close=last_close,
        last_pct=last_pct,
        avg_amount=avg_amt,
        capital_cny=capital_cny,
    )

    # Expected return channel (z-score based, not calibrated probability)
    exp_ret_lo = round(score * 0.15 - vol * 0.05, 2)
    exp_ret_hi = round(score * 0.25 + vol * 0.02, 2)
    downside_risk = round(min(15.0, vol * 1.2 + max(0, -float(row.get("ret_20", 0)) * 100) * 0.3), 2)
    crash_risk = round(min(1.0, (vol / 5.0) * 0.4 + (1.0 if last_pct <= -7 else 0.0) * 0.3), 3)
    liquidity_score = round(min(1.0, avg_amt / 5e8), 3)
    est_cost = estimate_round_trip_cost_cny(last_close, lots=1)
    uncertainty = round(min(1.0, 0.35 + vol / 8.0 + (0.15 if row.get("disclosure_flag") else 0)), 3)

    pos = neg = []
    if float(row.get("ret_20", 0)) > 0:
        pos.append(f"20日动量 +{float(row['ret_20'])*100:.1f}%")
    if float(row.get("trend", 0)) > 0:
        pos.append(f"价格高于20日均线 {float(row['trend'])*100:.1f}%")
    if vol > 3:
        neg.append(f"波动偏高 {vol:.1f}%")
    if row.get("disclosure_flag"):
        neg.append(f"公告风险 {row['disclosure_flag']}")
    if last_pct >= 9:
        neg.append("接近涨停，买入可行性差")

    lots, max_pos = affordable_lots(last_close, capital_cny)
    risk_penalty = downside_risk * 0.02 + crash_risk * 0.5 + uncertainty * 0.3
    cost_penalty = est_cost / max(capital_cny, 1) * 10
    final_score = round(score - risk_penalty - cost_penalty - (2.0 if not mask.valid_for_purchase else 0), 3)

    val = validation_status or {}
    reg = regime or {}
    eligibility = _eligibility(mask, val, uncertainty)

    return {
        **row,
        "rank": rank,
        "name": row.get("name", ""),
        "data_cutoff": as_of_date,
        "model_version": MODEL_VERSION,
        "forecast_horizon": FORECAST_HORIZON,
        "preset": preset,
        **mask.to_dict(),
        "expected_return_lo_pct": exp_ret_lo,
        "expected_return_hi_pct": exp_ret_hi,
        "downside_risk_pct": downside_risk,
        "crash_risk": crash_risk,
        "liquidity_score": liquidity_score,
        "estimated_round_trip_cost_cny": est_cost,
        "execution_risk": round(1.0 - liquidity_score, 3),
        "model_uncertainty": uncertainty,
        "positive_factors": pos,
        "negative_factors": neg,
        "factor_contributions": {
            "momentum_20d": round(float(row.get("ret_20", 0)) * 100, 2),
            "momentum_60d": round(float(row.get("ret_60", 0)) * 100, 2),
            "trend_vs_ma20": round(float(row.get("trend", 0)) * 100, 2),
            "volatility_penalty": round(vol, 2),
        },
        "regime_compatibility": reg.get("label", "UNKNOWN"),
        "validation_status": val.get("verdict", "NOT_RUN"),
        "purged_kfold_passed": val.get("purged_kfold_passed"),
        "affordable_lots": lots,
        "max_suggested_position_cny": max_pos,
        "suggested_qty": lots * 100 if lots else 0,
        "final_score": final_score,
        "alpha_score": round(score, 3),
        "eligibility": eligibility,
        "paper_status": "PAPER_ELIGIBLE" if eligibility in ("PAPER_ELIGIBLE", "SIMULATED_BROKER_ELIGIBLE") else "NOT_ELIGIBLE",
        "reasons_not_to_trade": _reasons_not_to_trade(mask, uncertainty, val),
        "invalidation_conditions": [
            "次日开盘涨停无法买入",
            "跌破20日均线且动量转负",
            "公告风险升级",
            "模型验证过期",
        ],
    }


def _eligibility(mask, val: dict, uncertainty: float) -> str:
    if not mask.valid_for_purchase:
        return "BLOCKED"
    if val.get("verdict") == "BLOCKED_BY_DATA":
        return "RESEARCH_ONLY"
    if uncertainty > 0.75:
        return "WATCHLIST_CANDIDATE"
    if val.get("verdict") in ("PASS", "CAUTION") and val.get("purged_kfold_passed"):
        return "PAPER_ELIGIBLE"
    if val.get("verdict") == "PASS":
        return "WATCHLIST_CANDIDATE"
    return "RESEARCH_ONLY"


def _reasons_not_to_trade(mask, uncertainty: float, val: dict) -> list[str]:
    reasons = list(mask.blockers)
    if uncertainty > 0.7:
        reasons.append("模型不确定性偏高")
    if val.get("verdict") == "BLOCKED_BY_DATA":
        reasons.append("验证数据不足")
    if not reasons:
        reasons.append("无硬性阻塞，仍需用户确认")
    return reasons
