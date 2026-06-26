"""RiskOS exposure snapshot."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def compute_exposure_report(positions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    positions = positions or []
    sector: dict[str, float] = {}
    for p in positions:
        sec = p.get("sector") or "未知"
        w = float(p.get("weight") or 0)
        sector[sec] = sector.get(sec, 0) + w
    max_sector = max(sector.values()) if sector else 0.0
    max_name = max((float(p.get("weight") or 0) for p in positions), default=0.0)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_positions": len(positions),
        "sector_exposure": sector,
        "max_sector_weight": round(max_sector, 4),
        "max_single_weight": round(max_name, 4),
        "portfolio_beta": None,
        "factor_exposure": {},
        "within_limits": max_sector <= 0.15 and max_name <= 0.05,
    }
