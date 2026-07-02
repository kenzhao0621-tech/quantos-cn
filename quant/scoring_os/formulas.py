"""Fixed total-score formula (v2.2 §5.2, §6):

FinalScore = BaseOpportunityScore × RegimeMultiplier × DataQualityMultiplier
             − RiskPenalty − ExecutionPenalty − OverheatPenalty

All factor scores are 0-100. Missing factors are neutral-scored (50) with their
weight halved (降权) and flagged — never silently filled with a high score. The
result carries a complete per-factor contribution breakdown for ExplainOS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from quant.scoring_os.normalization import NEUTRAL_SCORE, clamp_score, weighted_subscores
from quant.scoring_os.risk_penalty import (
    PenaltyResult,
    compute_execution_penalty,
    compute_overheat_penalty,
    compute_risk_penalty,
    hard_block_reasons,
)
from quant.scoring_os.weights import (
    BASE_WEIGHTS,
    FACTOR_LABELS_ZH,
    REGIME_MULTIPLIERS,
    SCORE_WEIGHT_VERSION,
    SOURCE_QUALITY_SCORE,
)

MISSING_FACTOR_WEIGHT_MULTIPLIER = 0.5

# v2.2 §5.4-§5.11 fixed sub-factor weights.
SUB_WEIGHTS: Dict[str, Dict[str, float]] = {
    "trend": {
        "ma_alignment": 0.35, "breakout": 0.25,
        "relative_strength": 0.20, "drawdown_recovery": 0.20,
    },
    "momentum": {
        "return_20d_percentile": 0.40, "return_60d_percentile": 0.30,
        "industry_relative_momentum": 0.30,
    },
    "volume_money_flow": {
        "volume_expansion": 0.30, "turnover_quality": 0.25,
        "money_flow": 0.25, "liquidity": 0.20,
    },
    "fundamental_quality": {
        "profitability": 0.25, "growth": 0.20, "balance_sheet": 0.20,
        "valuation_reasonableness": 0.20, "risk_flag": 0.15,
    },
    "announcement_policy": {
        "company_announcement": 0.40, "industry_policy": 0.35, "regulatory_risk": 0.25,
    },
    "sector_theme": {
        "sector_trend": 0.35, "sector_money_flow": 0.25,
        "policy_alignment": 0.20, "breadth": 0.20,
    },
    "kronos_forecast": {
        "direction_probability": 0.35, "expected_return": 0.25,
        "volatility_risk_adjusted": 0.20, "forecast_stability": 0.20,
    },
    "sentiment": {
        "news_sentiment": 0.40, "discussion_heat": 0.30, "sentiment_change": 0.30,
    },
}


def compose_factor(factor: str, sub_scores: Dict[str, Optional[float]]) -> Dict[str, Any]:
    """Compose a top-level factor score from its fixed sub-factor weights.

    Missing sub-scores are excluded and remaining weights renormalized; the
    breakdown records what was present.
    """
    weights = SUB_WEIGHTS[factor]
    pairs = []
    detail = []
    for sub, w in weights.items():
        s = sub_scores.get(sub)
        present = s is not None and s == s
        if present:
            pairs.append((w, float(s)))
        detail.append({
            "sub_factor": sub, "weight": w,
            "score": round(float(s), 2) if present else None,
            "missing": not present,
        })
    score = weighted_subscores(pairs) if pairs else NEUTRAL_SCORE
    return {
        "factor": factor,
        "score": round(score, 2),
        "sub_factors": detail,
        "all_missing": not pairs,
    }


@dataclass
class FactorScore:
    """One top-level factor entering BaseOpportunityScore."""

    name: str
    score: Optional[float]  # 0-100, None = unavailable
    source: str = ""
    source_url: str = ""
    updated_at: str = ""
    freshness: str = ""  # CacheOS FreshnessStatus value
    normalization: str = "robust_percentile_winsor_5_95"
    detail: Dict[str, Any] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.score is not None and self.score == self.score


@dataclass
class ScoreInputs:
    symbol: str
    factors: Dict[str, FactorScore]
    regime: str = "unknown"
    source_tiers: Dict[str, str] = field(default_factory=dict)  # factor -> tier key
    risk_inputs: Dict[str, Any] = field(default_factory=dict)
    execution_inputs: Dict[str, Any] = field(default_factory=dict)
    overheat_inputs: Dict[str, Any] = field(default_factory=dict)


def data_quality_multiplier(
    factors: Dict[str, FactorScore],
    source_tiers: Dict[str, str],
) -> Dict[str, Any]:
    """DataQualityMultiplier = min(1.00, weighted_source_quality) — v2.2 §6.2."""
    total_w = 0.0
    acc = 0.0
    per_factor = {}
    for name, w in BASE_WEIGHTS.items():
        fs = factors.get(name)
        tier = source_tiers.get(name, "")
        if fs is None or not fs.available:
            quality = SOURCE_QUALITY_SCORE["D_forbidden_or_missing"]
            tier = tier or "D_forbidden_or_missing"
        else:
            quality = SOURCE_QUALITY_SCORE.get(tier, SOURCE_QUALITY_SCORE["C_unverified"])
            tier = tier or "C_unverified"
        per_factor[name] = {"tier": tier, "quality": quality}
        acc += w * quality
        total_w += w
    multiplier = min(1.0, acc / total_w) if total_w else 0.0
    return {"multiplier": round(multiplier, 4), "per_factor": per_factor}


def compute_final_score(inputs: ScoreInputs) -> Dict[str, Any]:
    """Deterministic v2.2 total score with a full explanation payload.

    Same inputs always produce the same output (reproducibility test target).
    """
    # ---- BaseOpportunityScore with honest missing handling ----
    contributions: List[Dict[str, Any]] = []
    eff_pairs = []
    missing_factors: List[str] = []
    for name, w in BASE_WEIGHTS.items():
        fs = inputs.factors.get(name)
        if fs is not None and fs.available:
            score = clamp_score(float(fs.score))
            w_eff = w
            missing = False
        else:
            score = NEUTRAL_SCORE
            w_eff = w * MISSING_FACTOR_WEIGHT_MULTIPLIER
            missing = True
            missing_factors.append(name)
        eff_pairs.append((w_eff, score))
        contributions.append({
            "factor": name,
            "label_zh": FACTOR_LABELS_ZH.get(name, name),
            "weight": w,
            "effective_weight": round(w_eff, 4),
            "score": round(score, 2),
            "missing": missing,
            "source": fs.source if fs else "",
            "source_url": fs.source_url if fs else "",
            "updated_at": fs.updated_at if fs else "",
            "freshness": fs.freshness if fs else "unavailable",
            "normalization": fs.normalization if fs else "",
        })
    total_w = sum(w for w, _ in eff_pairs)
    base = sum(w * s for w, s in eff_pairs) / total_w if total_w else 0.0
    # Contribution shown to users: effective weight share × score.
    for c, (w_eff, s) in zip(contributions, eff_pairs):
        c["contribution"] = round((w_eff / total_w) * s, 2) if total_w else 0.0

    # ---- Multipliers ----
    regime_key = inputs.regime if inputs.regime in REGIME_MULTIPLIERS else "unknown"
    regime_mult = REGIME_MULTIPLIERS[regime_key]
    dq = data_quality_multiplier(inputs.factors, inputs.source_tiers)

    # ---- Penalties ----
    risk: PenaltyResult = compute_risk_penalty(inputs.risk_inputs)
    execution: PenaltyResult = compute_execution_penalty(inputs.execution_inputs)
    overheat: PenaltyResult = compute_overheat_penalty(inputs.overheat_inputs)
    blocks = hard_block_reasons(inputs.risk_inputs)

    final = base * regime_mult * dq["multiplier"] - risk.points - execution.points - overheat.points
    final = round(clamp_score(final), 2)

    return {
        "symbol": inputs.symbol,
        "score_weight_version": SCORE_WEIGHT_VERSION,
        "final_score": final,
        "base_opportunity_score": round(base, 2),
        "regime": regime_key,
        "regime_multiplier": regime_mult,
        "data_quality_multiplier": dq["multiplier"],
        "data_quality_per_factor": dq["per_factor"],
        "risk_penalty": risk.to_dict(),
        "execution_penalty": execution.to_dict(),
        "overheat_penalty": overheat.to_dict(),
        "contributions": contributions,
        "missing_factors": missing_factors,
        "hard_blocked": bool(blocks),
        "hard_block_reasons": blocks,
        "formula": (
            "FinalScore = BaseOpportunityScore × RegimeMultiplier × DataQualityMultiplier"
            " − RiskPenalty − ExecutionPenalty − OverheatPenalty"
        ),
    }
