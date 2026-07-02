"""Risk / execution / overheat penalties and hard do-not-buy blocks (v2.2 §6.3-6.5).

Each penalty takes structured sub-inputs already scaled 0-100 (0 = no risk,
100 = maximal risk) and maps them onto the documented point ranges:
  RiskPenalty      0-30 points
  ExecutionPenalty 0-15 points
  OverheatPenalty  0-20 points
Missing sub-inputs contribute zero penalty but are recorded so ExplainOS can
state which risk dimensions were not assessable (never hidden).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

RISK_PENALTY_MAX = 30.0
EXECUTION_PENALTY_MAX = 15.0
OVERHEAT_PENALTY_MAX = 20.0

RISK_WEIGHTS: Dict[str, float] = {
    "volatility_risk": 0.25,
    "drawdown_risk": 0.20,
    "fundamental_risk": 0.20,
    "event_risk": 0.15,
    "liquidity_risk": 0.10,
    "concentration_risk": 0.10,
}

EXECUTION_WEIGHTS: Dict[str, float] = {
    "lot_size": 0.30,
    "price_limit": 0.25,
    "slippage": 0.20,
    "t_plus_one": 0.15,
    "cash_fit": 0.10,
}

OVERHEAT_WEIGHTS: Dict[str, float] = {
    "short_term_return_overheat": 0.30,
    "volume_spike_risk": 0.25,
    "limit_up_chase_risk": 0.20,
    "valuation_overheat": 0.15,
    "sentiment_crowding_risk": 0.10,
}

# v2.2 §6.3 conditions that force 禁买/观察 regardless of score.
HARD_BLOCK_FLAGS: Dict[str, str] = {
    "is_st": "ST / *ST / 退市风险",
    "delisting_risk": "退市风险警示",
    "major_regulatory_penalty": "重大监管处罚",
    "non_standard_audit": "财报非标意见",
    "consecutive_limit_down": "连续跌停或流动性枯竭",
    "major_negative_announcement": "公告重大利空",
    "data_unverifiable": "数据不可验证",
}


@dataclass
class PenaltyResult:
    name: str
    points: float
    max_points: float
    components: List[Dict[str, Any]] = field(default_factory=list)
    missing_components: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "points": round(self.points, 2),
            "max_points": self.max_points,
            "components": self.components,
            "missing_components": self.missing_components,
        }


def _weighted_penalty(
    name: str,
    weights: Dict[str, float],
    inputs: Dict[str, Any],
    max_points: float,
) -> PenaltyResult:
    components: List[Dict[str, Any]] = []
    missing: List[str] = []
    acc = 0.0
    for sub, w in weights.items():
        raw = inputs.get(sub)
        if raw is None:
            missing.append(sub)
            components.append({"component": sub, "weight": w, "risk_0_100": None, "points": 0.0})
            continue
        risk = min(100.0, max(0.0, float(raw)))
        points = w * (risk / 100.0) * max_points
        acc += points
        components.append({
            "component": sub, "weight": w,
            "risk_0_100": round(risk, 1), "points": round(points, 2),
        })
    return PenaltyResult(
        name=name,
        points=min(max_points, acc),
        max_points=max_points,
        components=components,
        missing_components=missing,
    )


def compute_risk_penalty(inputs: Optional[Dict[str, Any]]) -> PenaltyResult:
    return _weighted_penalty("risk_penalty", RISK_WEIGHTS, inputs or {}, RISK_PENALTY_MAX)


def compute_execution_penalty(inputs: Optional[Dict[str, Any]]) -> PenaltyResult:
    return _weighted_penalty("execution_penalty", EXECUTION_WEIGHTS, inputs or {}, EXECUTION_PENALTY_MAX)


def compute_overheat_penalty(inputs: Optional[Dict[str, Any]]) -> PenaltyResult:
    return _weighted_penalty("overheat_penalty", OVERHEAT_WEIGHTS, inputs or {}, OVERHEAT_PENALTY_MAX)


def hard_block_reasons(risk_inputs: Optional[Dict[str, Any]]) -> List[str]:
    """Return the do-not-buy reasons triggered by hard flags."""
    inputs = risk_inputs or {}
    reasons = [label for flag, label in HARD_BLOCK_FLAGS.items() if inputs.get(flag)]
    # 短期涨幅过热且放量滞涨 — combination flag from overheat detection
    if inputs.get("overheat_stall"):
        reasons.append("短期涨幅过热且放量滞涨")
    return reasons
