"""Candidate-grade data readiness gate — CANDIDATE_DATA_READY."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from quant.historical_store import coverage_report
from quant.indices_store import load_index_summary


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
    gates.append({
        "name": "major_indices",
        "passed": idx.get("meets_minimum", False) or idx.get("available", 0) >= 3,
        "detail": f"{idx.get('available', 0)} indices persisted",
    })

    hist = coverage_report()
    gates.append({
        "name": "historical_bars",
        "passed": hist.get("partition_count", 0) >= 5,
        "detail": f"{hist.get('partition_count', 0)} partitions; need incremental backfill",
    })

    for g in gates:
        if not g["passed"]:
            reasons.append(f"{g['name']}: {g.get('detail', 'fail')}")

    ready = all(g["passed"] for g in gates)
    maturity = "CANDIDATE_DATA_READY" if ready else "PIPELINE_VERIFIED_WITH_DATA_GAPS"
    return CandidateReadinessResult(ready=ready, maturity=maturity, gates=gates, rejection_reasons=reasons)
