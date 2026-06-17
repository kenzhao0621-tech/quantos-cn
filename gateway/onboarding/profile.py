"""Investor and risk profiles — server-side, persisted locally."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT
from gateway.preferences import UserPreferences, load_preferences, save_preferences

PROFILE_PATH = ROOT / "data" / "gateway" / "investor_profile.json"


@dataclass
class InvestorProfile:
    goal: str = "balanced"  # preserve | steady | balanced | aggressive | custom
    total_budget_cny: float = 100000.0
    max_single_trade_cny: float = 20000.0
    max_acceptable_loss_cny: float = 8000.0
    max_daily_loss_cny: float = 2000.0
    max_single_position_pct: float = 0.18
    max_positions: int = 5
    allow_auto_trade: bool = False
    require_per_trade_confirm: bool = True
    price_min_cny: float = 0.0
    price_max_cny: float | None = None
    horizon: str = "3-10 sessions"
    exclude_st: bool = True
    exclude_low_liquidity: bool = True
    allow_chinext: bool = True
    allow_star: bool = False
    allow_bse: bool = False
    wizard_completed: bool = False
    wizard_step: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_investor_profile() -> InvestorProfile:
    if not PROFILE_PATH.exists():
        pref = load_preferences()
        return InvestorProfile(
            total_budget_cny=pref.capital_cny,
            max_acceptable_loss_cny=round(pref.capital_cny * pref.max_loss_pct, 2),
            max_single_position_pct=pref.max_single_position_pct,
            max_positions=pref.max_positions,
            price_min_cny=pref.price_min_cny,
            price_max_cny=pref.price_max_cny,
            horizon=pref.horizon,
        )
    raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    defaults = InvestorProfile().to_dict()
    defaults.update({k: v for k, v in raw.items() if k in defaults})
    return InvestorProfile(**defaults)  # type: ignore[arg-type]


def save_investor_profile(data: dict[str, Any]) -> InvestorProfile:
    current = load_investor_profile().to_dict()
    current.update({k: v for k, v in data.items() if k in current})
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    profile = InvestorProfile(**current)  # type: ignore[arg-type]
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    _sync_to_preferences(profile)
    return profile


def _sync_to_preferences(profile: InvestorProfile) -> UserPreferences:
    return save_preferences({
        "capital_cny": profile.total_budget_cny,
        "max_loss_pct": min(0.5, profile.max_acceptable_loss_cny / max(profile.total_budget_cny, 1000)),
        "max_positions": profile.max_positions,
        "max_single_position_pct": profile.max_single_position_pct,
        "price_min_cny": profile.price_min_cny,
        "price_max_cny": profile.price_max_cny,
        "horizon": profile.horizon,
        "strategy_preset": _goal_to_preset(profile.goal),
    })


def _goal_to_preset(goal: str) -> str:
    return {
        "preserve": "defensive",
        "steady": "defensive",
        "balanced": "balanced",
        "aggressive": "momentum",
    }.get(goal, "balanced")


def strategy_proposals() -> list[dict[str, Any]]:
    """Three beginner-facing strategy options with honest limits."""
    return [
        {
            "id": "steady",
            "label": "稳健",
            "goal": "保住本金优先",
            "risk": "低",
            "market_fit": "震荡市、下跌市",
            "failure_mode": "强势单边上涨可能跑输指数",
            "preset": "defensive",
            "confidence": "medium",
        },
        {
            "id": "balanced",
            "label": "平衡",
            "goal": "收益与风险平衡",
            "risk": "中",
            "market_fit": "多数市场环境",
            "failure_mode": "极端行情下回撤仍可能超预期",
            "preset": "balanced",
            "confidence": "medium",
        },
        {
            "id": "aggressive",
            "label": "积极",
            "goal": "接受较高波动",
            "risk": "高",
            "market_fit": "趋势明朗的上行市",
            "failure_mode": "震荡市频繁止损、换手成本高",
            "preset": "momentum",
            "confidence": "low",
        },
    ]


def beginner_daily_summary() -> dict[str, Any]:
    """One-screen beginner report from system status."""
    from gateway.observability.platform_health import get_platform_health
    from gateway.preferences import affordability_budget, load_preferences

    pref = load_preferences()
    health = get_platform_health()
    aff = affordability_budget(pref)
    return {
        "headline": "今日系统状态",
        "capital_cny": pref.capital_cny,
        "affordability": aff,
        "data_gate": health.get("data_gate", {}).get("verdict"),
        "promotion_stage": health.get("promotion", {}).get("stage"),
        "actions": [
            "若尚未完成新手配置，请先运行五步向导",
            "生成订单票据前建议先进入 Paper 模拟",
            "所有真实交易需在券商官方客户端人工确认",
        ],
        "risks": [
            "数据可能延迟，不可当作实时行情交易依据",
            "模型历史表现不代表未来收益",
        ],
    }
