"""Real sector rotation from AKShare industry boards."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.china_quant.models import SectorInfo


@dataclass
class SectorRankingReport:
    analysis_date: str
    mode: str
    sectors: list[SectorInfo] = field(default_factory=list)
    provider: str = "akshare"


def rank_sectors_from_boards(board_rows: list[dict], *, top_n: int = 15) -> list[SectorInfo]:
    """AKShare stock_board_industry_name_em columns: 板块名称, 涨跌幅, 总市值, 换手率, 上涨家数, 下跌家数"""
    sectors: list[SectorInfo] = []
    for r in board_rows:
        name = str(r.get("板块名称", r.get("name", "")))
        if not name:
            continue
        chg = float(r.get("涨跌幅", r.get("change_pct", 0)) or 0)
        up = int(r.get("上涨家数", 0) or 0)
        down = int(r.get("下跌家数", 0) or 0)
        total = up + down
        breadth = up / total * 100 if total else 50
        phase = "early" if chg > 2 and breadth > 60 else "overheated" if chg > 5 else "mature" if chg > 0 else "reversing"
        if abs(chg) < 0.3 and total > 0:
            phase = "insufficient_data" if total < 5 else "mature"
        sectors.append(
            SectorInfo(
                name=name,
                strength_score=min(100, 50 + chg * 5 + breadth * 0.3),
                momentum_pct=chg,
                breadth_pct=breadth,
                phase=phase if phase != "insufficient_data" else "mature",
                thesis=f"板块涨跌幅{chg:+.2f}%，广度{breadth:.0f}%",
                invalidation="板块指数跌破5日均线或广度转弱",
                catalyst_status="speculative",
            )
        )
    sectors.sort(key=lambda s: s.strength_score, reverse=True)
    return sectors[:top_n]


def render_sector_report(report: SectorRankingReport) -> str:
    lines = [
        f"# Sector Ranking — {report.analysis_date}",
        "",
        f"- Mode: {report.mode}",
        f"- Provider: {report.provider}",
        "",
    ]
    for i, s in enumerate(report.sectors, 1):
        lines += [
            f"## {i}. {s.name}",
            f"- Score: {s.strength_score:.0f}",
            f"- Momentum: {s.momentum_pct:+.2f}%",
            f"- Breadth: {s.breadth_pct:.0f}%",
            f"- Stage: {s.phase.upper()}",
            f"- Thesis: {s.thesis}",
            "",
        ]
    return "\n".join(lines)
