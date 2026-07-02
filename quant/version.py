"""Single source of truth for model/engine version strings.

Refactor audit MODEL_AUDIT §1: three version strings coexisted
(v4_industry_neutral / v5_ensemble_lgbm / v6_trading_agents_zh).
All modules must import from here.
"""

from __future__ import annotations

SCREENER_MODEL_VERSION = "screener_v7_quantos2_2026-07-02"
SCREENER_ENGINE = "screener_v7_quantos2"
FEATURE_BLEND_NAME = "price_momentum_lite"  # NOT full Alpha158 — 5-factor composite
ALPHA158_FEATURE_VERSION = "alpha158_compatible_v1"
