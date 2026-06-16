"""Sector rotation with stage classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.china_quant.models import SectorInfo


STAGE_MAP = {
    "early": "EARLY",
    "developing": "DEVELOPING",
    "mature": "MATURE",
    "overheated": "OVERHEATED",
    "reversing": "REVERSING",
}


@dataclass
class SectorRotationResult:
    ranked: list[SectorInfo]
    top_names: set[str]


def classify_stage(s: SectorInfo) -> str:
    return STAGE_MAP.get(s.phase, "INSUFFICIENT_DATA")


def rank_sectors_v2(sectors: list[SectorInfo], top_n: int = 5) -> SectorRotationResult:
    def score(s: SectorInfo) -> float:
        stage_bonus = {"early": 8, "developing": 5, "mature": 0, "overheated": -12, "reversing": -8}.get(s.phase, 0)
        cat = 6 if s.catalyst_status == "confirmed" else 0
        return s.strength_score + s.momentum_pct * 2 + s.breadth_pct * 0.15 + stage_bonus + cat

    ranked = sorted(sectors, key=score, reverse=True)[:top_n]
    return SectorRotationResult(ranked, {s.name for s in ranked[:3]})
