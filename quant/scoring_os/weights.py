"""Versioned score weights (v2.2 §5.2). Weights live in config + code, never LLM."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
WEIGHTS_CONFIG = ROOT / "config" / "score_weights.yaml"

SCORE_WEIGHT_VERSION = "v2.3_integrated_conservative_ashare"

# v2.2 §5.2 BaseOpportunityScore weights — must sum to 1.0.
BASE_WEIGHTS: Dict[str, float] = {
    "trend": 0.20,
    "momentum": 0.15,
    "volume_money_flow": 0.15,
    "fundamental_quality": 0.15,
    "announcement_policy": 0.10,
    "sector_theme": 0.10,
    "kronos_forecast": 0.10,
    "sentiment": 0.05,
}

FACTOR_LABELS_ZH: Dict[str, str] = {
    "trend": "趋势",
    "momentum": "动量",
    "volume_money_flow": "量价资金",
    "fundamental_quality": "基本面",
    "announcement_policy": "公告政策",
    "sector_theme": "板块主题",
    "kronos_forecast": "Kronos预测",
    "sentiment": "情绪",
}

WEIGHT_RATIONALE_ZH: Dict[str, str] = {
    "trend": "技术面与趋势合计 35%，避免纯消息驱动",
    "momentum": "动量属于技术面 35% 的组成部分，同时受过热惩罚约束",
    "volume_money_flow": "资金量价 15%，识别是否有真实交易支持",
    "fundamental_quality": "基本面 15%，过滤垃圾股与高风险公司",
    "announcement_policy": "公告政策 10%（与板块主题合计 20%），适配国内政策行情",
    "sector_theme": "板块主题 10%，适配主题行情但检查过热",
    "kronos_forecast": "Kronos 10%，只做预测辅助，不单独决定买卖",
    "sentiment": "情绪 5%，只做边际修正，防股吧/微博噪声",
}

# v2.2 §6.1 RegimeMultiplier
REGIME_MULTIPLIERS: Dict[str, float] = {
    "strong_bull": 1.15,
    "structural_bull": 1.05,
    "range_bound": 1.00,
    "weak_range": 0.85,
    "bear": 0.65,
    "unknown": 0.85,  # unknown regime treated conservatively, never optimistically
}

# v2.2 §6.2 source quality tiers for DataQualityMultiplier
SOURCE_QUALITY_SCORE: Dict[str, float] = {
    "S_official_exchange": 1.00,
    "A_public_data_vendor": 0.90,
    "B_news_sentiment": 0.70,
    "C_unverified": 0.40,
    "D_forbidden_or_missing": 0.00,
}


def get_weight_set(version: str = SCORE_WEIGHT_VERSION) -> Dict[str, Any]:
    """Return the named weight set. Only versions defined in code/config exist —
    asking for an unknown version raises instead of silently inventing weights."""
    if version != SCORE_WEIGHT_VERSION:
        raise KeyError(f"unknown score_weight_version: {version}")
    return {
        "score_weight_version": SCORE_WEIGHT_VERSION,
        "weights": dict(BASE_WEIGHTS),
        "labels_zh": dict(FACTOR_LABELS_ZH),
        "rationale_zh": dict(WEIGHT_RATIONALE_ZH),
        "regime_multipliers": dict(REGIME_MULTIPLIERS),
        "source_quality_score": dict(SOURCE_QUALITY_SCORE),
    }
