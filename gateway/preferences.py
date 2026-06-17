"""User trading preferences for the local portal.

These are local, non-secret settings: capital, risk budget, position count, and
selection defaults. They intentionally do not enable real-money execution.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gateway.config import ROOT

PREF_PATH = ROOT / "data" / "gateway" / "user_preferences.json"


@dataclass
class UserPreferences:
    capital_cny: float = 100000.0
    max_loss_pct: float = 0.08
    max_positions: int = 5
    max_single_position_pct: float = 0.18
    cash_buffer_pct: float = 0.20
    min_amount_cny: float = 100000000.0
    strategy_preset: str = "balanced"
    horizon: str = "3-10 sessions"
    preferred_sectors: list[str] = field(default_factory=list)
    excluded_sectors: list[str] = field(default_factory=list)
    price_min_cny: float = 0.0
    price_max_cny: float | None = None
    enforce_capital_price_ceiling: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["preferred_sectors"] = self.preferred_sectors or []
        data["excluded_sectors"] = self.excluded_sectors or []
        return data


def load_preferences() -> UserPreferences:
    if not PREF_PATH.exists():
        return UserPreferences()
    raw = json.loads(PREF_PATH.read_text(encoding="utf-8"))
    defaults = UserPreferences().to_dict()
    defaults.update({k: v for k, v in raw.items() if k in defaults})
    return UserPreferences(
        capital_cny=max(1000.0, float(defaults["capital_cny"])),
        max_loss_pct=max(0.001, min(float(defaults["max_loss_pct"]), 0.50)),
        max_positions=max(1, min(int(defaults["max_positions"]), 30)),
        max_single_position_pct=max(0.01, min(float(defaults["max_single_position_pct"]), 0.80)),
        cash_buffer_pct=max(0.0, min(float(defaults["cash_buffer_pct"]), 0.90)),
        min_amount_cny=max(0.0, float(defaults["min_amount_cny"])),
        strategy_preset=str(defaults["strategy_preset"] or "balanced"),
        horizon=str(defaults["horizon"] or "3-10 sessions"),
        preferred_sectors=_norm_sector_list(defaults.get("preferred_sectors", [])),
        excluded_sectors=_norm_sector_list(defaults.get("excluded_sectors", [])),
        price_min_cny=max(0.0, float(defaults.get("price_min_cny", 0) or 0)),
        price_max_cny=_optional_float(defaults.get("price_max_cny")),
        enforce_capital_price_ceiling=bool(defaults.get("enforce_capital_price_ceiling", True)),
    )


def save_preferences(data: dict[str, Any]) -> UserPreferences:
    current = load_preferences().to_dict()
    current.update({k: v for k, v in data.items() if k in current})
    pref = UserPreferences(
        capital_cny=max(1000.0, float(current["capital_cny"])),
        max_loss_pct=max(0.001, min(float(current["max_loss_pct"]), 0.50)),
        max_positions=max(1, min(int(current["max_positions"]), 30)),
        max_single_position_pct=max(0.01, min(float(current["max_single_position_pct"]), 0.80)),
        cash_buffer_pct=max(0.0, min(float(current["cash_buffer_pct"]), 0.90)),
        min_amount_cny=max(0.0, float(current["min_amount_cny"])),
        strategy_preset=str(current["strategy_preset"] or "balanced"),
        horizon=str(current["horizon"] or "3-10 sessions"),
        preferred_sectors=_norm_sector_list(current.get("preferred_sectors", [])),
        excluded_sectors=_norm_sector_list(current.get("excluded_sectors", [])),
        price_min_cny=max(0.0, float(current.get("price_min_cny", 0) or 0)),
        price_max_cny=_optional_float(current.get("price_max_cny")),
        enforce_capital_price_ceiling=bool(current.get("enforce_capital_price_ceiling", True)),
    )
    PREF_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREF_PATH.write_text(json.dumps(pref.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return pref


def apply_preferences_to_risk(risk: Any, pref: UserPreferences | None = None) -> None:
    """Patch the in-memory risk engine with local user settings."""
    pref = pref or load_preferences()
    risk.config.capital.total_allocated_cny = pref.capital_cny
    risk.config.capital.absolute_max_cumulative_loss_cny = round(pref.capital_cny * pref.max_loss_pct, 2)
    risk.config.capital.protected_capital_floor_cny = round(pref.capital_cny * (1 - pref.max_loss_pct), 2)
    risk.config.risk.max_open_positions = pref.max_positions
    risk.config.risk.maximum_single_name_risk_pct = pref.max_single_position_pct
    risk.config.risk.minimum_cash_buffer_pct = pref.cash_buffer_pct
    if hasattr(risk, "_equity") and risk._equity < risk.config.capital.protected_capital_floor_cny:
        # Local preference changes are not historical PnL; keep runtime equity
        # coherent with the user's configured paper capital.
        risk._equity = pref.capital_cny


def _norm_sector_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.replace("，", ",").split(",")
    elif isinstance(value, list):
        parts = value
    else:
        parts = []
    return [str(x).strip() for x in parts if str(x).strip()]


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        f = float(value)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None
