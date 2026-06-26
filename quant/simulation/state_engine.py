"""Market State Engine — regime + liquidity + policy tone from observable data."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def build_market_state(*, as_of_date: str | None = None) -> dict[str, Any]:
    from quant.regime import load_regime_from_warehouse

    reg = load_regime_from_warehouse()
    label = reg.get("label", "sideway")
    vol = reg.get("index_vol_20", 0.02)
    liquidity = "high" if reg.get("market_breadth", 0.5) > 0.55 else "medium" if reg.get("market_breadth", 0.5) > 0.45 else "low"
    volatility = "high" if vol > 0.025 else "low" if vol < 0.015 else "medium"

    regime_map = {
        "bull": "bull",
        "bear": "bear",
        "panic": "high_volatility",
        "sideway": "sideways",
    }
    return {
        "date": as_of_date or reg.get("as_of_date"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "regime": regime_map.get(label, label),
        "liquidity": liquidity,
        "volatility": volatility,
        "policy_tone": {"default": "neutral"},
        "sector_rotation": reg.get("sector_hints") or {},
        "risk_appetite": "low" if label in ("bear", "panic") else "medium",
        "macro_pressure": "elevated" if label == "panic" else "normal",
        "theme_strength": {},
        "forbidden_outputs": ["BUY", "SELL", "HOLD", "target_price", "guaranteed_return"],
    }
