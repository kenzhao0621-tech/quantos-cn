"""Human-readable score breakdown (v2.2 §8.3) built from compute_final_score output."""

from __future__ import annotations

from typing import Any, Dict, List


def build_score_breakdown(score_result: Dict[str, Any]) -> Dict[str, Any]:
    """Render the §8.3 breakdown block. Purely a projection — no recomputation."""
    lines: List[str] = [f"综合评分：{score_result['final_score']} / 100"]
    rows: List[Dict[str, Any]] = []
    for c in score_result.get("contributions", []):
        label = c.get("label_zh") or c["factor"]
        suffix = "（数据缺失，按中性50降权）" if c.get("missing") else ""
        lines.append(f"{label}：{c['score']:.0f}，贡献 +{c['contribution']:.1f}{suffix}")
        rows.append({
            "factor": c["factor"],
            "label_zh": label,
            "weight": c["weight"],
            "effective_weight": c["effective_weight"],
            "score": c["score"],
            "contribution": c["contribution"],
            "missing": c.get("missing", False),
            "source": c.get("source", ""),
            "source_url": c.get("source_url", ""),
            "updated_at": c.get("updated_at", ""),
            "freshness": c.get("freshness", ""),
            "normalization": c.get("normalization", ""),
        })
    risk = score_result.get("risk_penalty", {})
    execu = score_result.get("execution_penalty", {})
    heat = score_result.get("overheat_penalty", {})
    lines.extend([
        f"市场环境乘数：{score_result.get('regime_multiplier')}",
        f"数据质量乘数：{score_result.get('data_quality_multiplier')}",
        f"风险惩罚：-{risk.get('points', 0)}",
        f"执行惩罚：-{execu.get('points', 0)}",
        f"过热惩罚：-{heat.get('points', 0)}",
        f"最终分：{score_result['final_score']}",
    ])
    return {
        "final_score": score_result["final_score"],
        "base_opportunity_score": score_result.get("base_opportunity_score"),
        "score_weight_version": score_result.get("score_weight_version"),
        "formula": score_result.get("formula"),
        "factors": rows,
        "regime_multiplier": score_result.get("regime_multiplier"),
        "data_quality_multiplier": score_result.get("data_quality_multiplier"),
        "risk_penalty_points": risk.get("points", 0),
        "execution_penalty_points": execu.get("points", 0),
        "overheat_penalty_points": heat.get("points", 0),
        "penalty_details": {"risk": risk, "execution": execu, "overheat": heat},
        "missing_factors": score_result.get("missing_factors", []),
        "text_lines": lines,
    }
