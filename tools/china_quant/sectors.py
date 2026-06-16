"""Sector ranking."""

from __future__ import annotations

from tools.china_quant.models import SectorInfo


def rank_sectors(sectors: list[SectorInfo], top_n: int = 5) -> list[SectorInfo]:
    def key(s: SectorInfo) -> float:
        phase_penalty = {"overheated": -15, "mature": 0, "early": 5}.get(s.phase, 0)
        catalyst_bonus = 5 if s.catalyst_status == "confirmed" else 0
        return s.strength_score + s.momentum_pct * 2 + s.breadth_pct * 0.1 + phase_penalty + catalyst_bonus

    ranked = sorted(sectors, key=key, reverse=True)
    return ranked[:top_n]
