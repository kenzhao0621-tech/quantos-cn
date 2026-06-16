"""Staged disclosure enrichment A→D."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from quant.disclosures.policy import evaluate_symbol_disclosures
from quant.disclosures.pit_filter import filter_point_in_time


@dataclass
class EnrichmentReport:
    stage_a_flags: dict[str, Any] = field(default_factory=dict)
    stage_b_symbols: list[str] = field(default_factory=list)
    stage_c_watchlist: list[str] = field(default_factory=list)
    stage_d_final: Optional[dict[str, Any]] = None
    symbol_evaluations: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_a": self.stage_a_flags,
            "stage_b_count": len(self.stage_b_symbols),
            "stage_c_watchlist": self.stage_c_watchlist,
            "stage_d": self.stage_d_final,
            "symbol_evaluations": self.symbol_evaluations,
        }


def run_staged_enrichment(
    *,
    all_rows: list[dict[str, Any]],
    preliminary_top50: list[str],
    watchlist_top10: list[str],
    final_candidate: Optional[str],
    analysis_cutoff: str,
) -> EnrichmentReport:
    pit = filter_point_in_time(all_rows, analysis_cutoff=analysis_cutoff)
    eligible = pit.passed
    report = EnrichmentReport(
        stage_a_flags={"pit_passed": len(eligible), "pit_rejected": len(pit.rejected)},
        stage_b_symbols=preliminary_top50[:50],
        stage_c_watchlist=watchlist_top10[:10],
    )
    for sym in watchlist_top10[:10]:
        ev = evaluate_symbol_disclosures(sym, eligible)
        report.symbol_evaluations[sym] = ev.to_dict()
    if final_candidate:
        ev = evaluate_symbol_disclosures(final_candidate, eligible)
        report.stage_d_final = ev.to_dict()
    return report
