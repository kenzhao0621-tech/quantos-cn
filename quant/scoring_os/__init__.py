"""ScoringOS — fixed, reproducible, explainable A-share scoring formula (v2.2 §5-7).

Principles (v2.2 §5.1):
  1. the formula is fixed in code, never improvised by an LLM;
  2. every factor carries definition, source, updated_at, direction, normalization;
  3. every weight set is versioned; 4. no future data in tuning; 5. no
  unconstrained return-maximising weight search; 6. every recommendation
  explains per-factor contributions; 7. the formula is allowed to say
  "no recommendation today".
"""

from quant.scoring_os.weights import (
    SCORE_WEIGHT_VERSION,
    BASE_WEIGHTS,
    get_weight_set,
)
from quant.scoring_os.formulas import FactorScore, ScoreInputs, compute_final_score
from quant.scoring_os.confidence import compute_confidence
from quant.scoring_os.target_price import build_trade_plan

__all__ = [
    "SCORE_WEIGHT_VERSION",
    "BASE_WEIGHTS",
    "get_weight_set",
    "FactorScore",
    "ScoreInputs",
    "compute_final_score",
    "compute_confidence",
    "build_trade_plan",
]
