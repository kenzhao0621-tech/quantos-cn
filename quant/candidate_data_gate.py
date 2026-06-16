"""Candidate-grade data readiness gate — CANDIDATE_DATA_READY."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from quant.disclosure_store import disclosure_coverage_report
from quant.fundamental_store import fundamental_coverage_report
from quant.historical_store import coverage_report
from quant.indices_store import load_index_summary
from quant.sector_store import sector_coverage_report


@dataclass
class CandidateReadinessResult:
    ready: bool
    maturity: str
    gates: list[dict[str, Any]] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_candidate_readiness(
    *,
    run_id: str,
    spot_row_count: int,
    spot_provider: str,
    quality_passed: bool,
    is_fixture: bool = False,
    is_manual: bool = False,
) -> CandidateReadinessResult:
    gates: list[dict[str, Any]] = []
    reasons: list[str] = []

    gates.append({"name": "spot_full_market", "passed": spot_row_count >= 5000, "detail": str(spot_row_count)})
    gates.append({"name": "quality_passed", "passed": quality_passed})
    gates.append({"name": "non_fixture", "passed": not is_fixture and not is_manual})
    gates.append({"name": "run_id_bound", "passed": bool(run_id)})

    idx = load_index_summary()
    idx_with_120 = sum(1 for v in idx.get("indices", {}).values() if v.get("bars", 0) >= 120)
    gates.append({
        "name": "major_indices",
        "passed": idx_with_120 >= 3,
        "detail": f"{idx_with_120} indices with >=120 bars",
    })

    hist = coverage_report()
    part_count = hist.get("partition_count", 0)
    gates.append({
        "name": "historical_bars",
        "passed": part_count >= 60,
        "detail": f"{part_count} partitions (need >=60 trade dates)",
    })

    sectors = sector_coverage_report()
    gates.append({
        "name": "sector_classification",
        "passed": sectors.get("total_rows", 0) >= 3000,
        "detail": f"{sectors.get('total_rows', 0)} sector rows",
    })

    fundamentals = fundamental_coverage_report()
    gates.append({
        "name": "fundamentals",
        "passed": fundamentals.get("total_rows", 0) >= 1000,
        "detail": f"{fundamentals.get('total_rows', 0)} fundamental rows",
    })

    disclosures = disclosure_coverage_report()
    gates.append({
        "name": "disclosures",
        "passed": disclosures.get("total_rows", 0) >= 50,
        "detail": f"{disclosures.get('total_rows', 0)} disclosure rows",
    })

    for g in gates:
        if not g["passed"]:
            reasons.append(f"{g['name']}: {g.get('detail', 'fail')}")

    ready = all(g["passed"] for g in gates)
    maturity = "CANDIDATE_DATA_READY" if ready else "PIPELINE_VERIFIED_WITH_DATA_GAPS"
    return CandidateReadinessResult(ready=ready, maturity=maturity, gates=gates, rejection_reasons=reasons)
