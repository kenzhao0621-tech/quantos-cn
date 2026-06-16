"""Production verification and next-trading-day quant research."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
LEDGER_DIR = ROOT / "docs" / "ai" / "daily-trading"

THRESHOLDS = {
    "minimum_rows": 5000,
    "valid_symbol_ratio_min": 0.99,
    "valid_price_ratio_min": 0.95,
    "duplicate_symbol_ratio_max": 0.001,
    "risk_on_min_score": 78,
    "neutral_min_score": 84,
    "risk_off_min_score": 92,
    "minimum_reward_to_risk": 2.0,
}

REQUIRED_INDEX_KEYS = [
    "sh",  # SSE Composite
    "csi300",
    "csi500",
    "csi1000",
    "star50",
    "chinext",
    "szci",
]

CRITICAL_DATASETS = [
    "spot_quotes",
    "trading_calendar",
    "indices",
]


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str = ""
    severity: str = "required"  # required | advisory


@dataclass
class BreadthMetrics:
    advancers: int = 0
    decliners: int = 0
    unchanged: int = 0
    advance_decline_ratio: float = 0.0
    limit_up_count: int = 0
    limit_down_count: int = 0
    median_return: float = 0.0
    pct_above_ma20: Optional[float] = None


@dataclass
class ResearchDecision:
    decision: str  # TRADE_CANDIDATE | NO_TRADE | BLOCKED_*
    run_id: str
    analysis_date: str
    data_date: str
    target_trading_date: str
    generated_at: str
    calendar_provider: str
    spot_provider: str
    row_count: int = 0
    quality_status: str = ""
    freshness: str = ""
    market_regime: str = ""
    regime_score: float = 0.0
    regime_confidence: str = ""
    candidate: Optional[dict[str, Any]] = None
    rejection_reasons: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    gates: list[dict[str, Any]] = field(default_factory=list)
    breadth: Optional[dict[str, Any]] = None
    ledger_result: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_cal_day(d: str) -> str:
    if "-" in d:
        return d
    if len(d) == 8:
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return d


def next_open_trading_day(calendar_days: list[str], after: str) -> str:
    normed = sorted(_normalize_cal_day(d) for d in calendar_days)
    for d in normed:
        if d > after:
            return d
    return "unknown"


def latest_completed_market_date(calendar_days: list[str], as_of: str) -> str:
    normed = sorted(_normalize_cal_day(d) for d in calendar_days)
    candidates = [d for d in normed if d <= as_of]
    return candidates[-1] if candidates else as_of


def compute_breadth(spot_rows: list[dict[str, Any]]) -> BreadthMetrics:
    if not spot_rows:
        return BreadthMetrics()
    changes = [float(r.get("change_pct") or 0) for r in spot_rows]
    adv = sum(1 for c in changes if c > 0)
    dec = sum(1 for c in changes if c < 0)
    unch = len(changes) - adv - dec
    sorted_c = sorted(changes)
    med = sorted_c[len(sorted_c) // 2]
    return BreadthMetrics(
        advancers=adv,
        decliners=dec,
        unchanged=unch,
        advance_decline_ratio=adv / max(dec, 1),
        limit_up_count=sum(1 for c in changes if c >= 9.5),
        limit_down_count=sum(1 for c in changes if c <= -9.5),
        median_return=med,
    )


def classify_regime_label(
    breadth: BreadthMetrics,
    index_chg: Optional[float],
    *,
    available_indices: int,
) -> tuple[str, float, str, list[str], list[str]]:
    supporting: list[str] = []
    opposing: list[str] = []
    score = 50.0

    if breadth.advance_decline_ratio >= 1.2:
        score += 15
        supporting.append(f"A/D ratio {breadth.advance_decline_ratio:.2f}")
    elif breadth.advance_decline_ratio < 0.85:
        score -= 20
        opposing.append(f"Weak breadth A/D {breadth.advance_decline_ratio:.2f}")

    if index_chg is not None:
        supporting.append(f"SSE 1d change {index_chg:+.2f}%")
        score += max(-15, min(15, index_chg * 5))
    else:
        opposing.append("SSE index change unavailable")
        score -= 10

    if breadth.limit_down_count > breadth.limit_up_count * 1.5:
        score -= 15
        opposing.append("Limit-down exceeds limit-up")
    if breadth.limit_up_count > breadth.limit_down_count * 1.5:
        score += 10
        supporting.append("Limit-up breadth positive")

    if available_indices < 3:
        score -= 20
        opposing.append(f"Only {available_indices} major index benchmark(s) available")

    if score >= 65:
        label = "RISK_ON"
    elif score >= 45:
        label = "NEUTRAL"
    elif score >= 30:
        label = "RISK_OFF"
    else:
        label = "DISORDERED"

    confidence = "HIGH" if available_indices >= 3 and index_chg is not None else "LOW"
    if available_indices < 2:
        confidence = "LOW"
    return label, score, confidence, supporting, opposing


def _norm_code(code: Any) -> str:
    c = str(code).lower().strip()
    for prefix in ("sh", "sz", "bj"):
        if c.startswith(prefix):
            c = c[len(prefix):]
    return c.zfill(6)


def verify_snapshot_gates(
    run_id: str,
    spot_doc: dict[str, Any],
    manifest: dict[str, Any],
) -> list[GateResult]:
    gates: list[GateResult] = []
    payload = spot_doc.get("payload", {})
    rows = payload.get("rows", [])
    row_count = len(rows)

    gates.append(GateResult(
        "run_id_match",
        manifest.get("run_id") == run_id,
        f"manifest={manifest.get('run_id')}",
    ))
    gates.append(GateResult(
        "non_fixture",
        not manifest.get("is_fixture") and manifest.get("provider") != "manual_snapshot",
        manifest.get("provider", ""),
    ))
    gates.append(GateResult(
        "row_count",
        row_count >= THRESHOLDS["minimum_rows"],
        f"{row_count} vs min {THRESHOLDS['minimum_rows']}",
    ))

    codes = [_norm_code(r.get("code", "")) for r in rows]
    valid_symbols = sum(1 for c in codes if len(c) == 6 and c.isdigit())
    gates.append(GateResult(
        "valid_symbol_ratio",
        valid_symbols / max(row_count, 1) >= THRESHOLDS["valid_symbol_ratio_min"],
        f"{valid_symbols / max(row_count, 1):.4f}",
    ))
    valid_price = sum(1 for r in rows if float(r.get("price") or 0) > 0)
    gates.append(GateResult(
        "valid_price_ratio",
        valid_price / max(row_count, 1) >= THRESHOLDS["valid_price_ratio_min"],
        f"{valid_price / max(row_count, 1):.4f}",
    ))
    dup = row_count - len(set(codes))
    gates.append(GateResult(
        "duplicate_ratio",
        dup / max(row_count, 1) <= THRESHOLDS["duplicate_symbol_ratio_max"],
        f"duplicates={dup}",
    ))
    gates.append(GateResult(
        "provenance_hash",
        bool(manifest.get("data_hash")),
        manifest.get("data_hash", "")[:16],
    ))
    gates.append(GateResult(
        "market_date_known",
        bool(manifest.get("market_date") or payload.get("market_date")),
        str(manifest.get("market_date") or payload.get("market_date")),
    ))
    return gates


def verify_supporting_datasets(run_id: str) -> list[GateResult]:
    from quant.data_lake import DATA_ROOT, load_by_run_id

    gates: list[GateResult] = []
    for ds in CRITICAL_DATASETS:
        doc = load_by_run_id(ds, run_id)
        gates.append(GateResult(f"dataset_{ds}", doc is not None, "present" if doc else "missing"))

    manifest_path = DATA_ROOT / "manifests" / run_id / "security_master.manifest.json"
    gates.append(GateResult(
        "security_master",
        manifest_path.exists(),
        "persisted" if manifest_path.exists() else "not fetched in snapshot",
        severity="advisory",
    ))

    bars_path = DATA_ROOT / "manifests" / run_id / "historical_bars.manifest.json"
    gates.append(GateResult(
        "historical_bars",
        bars_path.exists(),
        "not persisted — required for per-stock bar-complete gate",
        severity="candidate",
    ))

    idx_doc = load_by_run_id("indices", run_id) or {}
    idx_payload = idx_doc.get("payload", {})
    benchmark_keys = [k for k in idx_payload if k not in ("source_dataset", "endpoint")]
    available = len(benchmark_keys)
    gates.append(GateResult(
        "major_indices_coverage",
        available >= 3,
        f"{available}/{len(REQUIRED_INDEX_KEYS)} benchmarks; have={benchmark_keys}",
        severity="candidate",
    ))

    sec_doc = load_by_run_id("sector_boards", run_id) or {}
    sec_rows = len(sec_doc.get("payload", {}).get("rows", []))
    gates.append(GateResult(
        "sector_boards_scale",
        sec_rows >= 30,
        f"{sec_rows} sector rows",
        severity="advisory",
    ))
    return gates


def verify_ledger(run_id: str, base: Path = LEDGER_DIR) -> list[GateResult]:
    from quant.paper_ledger import find_records_by_run_id, run_id_in_ledger

    gates: list[GateResult] = []
    in_ledger = run_id_in_ledger(base, run_id)
    recs = find_records_by_run_id(base, run_id)
    gates.append(GateResult("ledger_appended", in_ledger, f"{len(recs)} record(s)"))
    if recs:
        r = recs[0]
        gates.append(GateResult("ledger_has_run_id", r.get("run_id") == run_id, r.get("run_id", "")))
        gates.append(GateResult("ledger_has_provider", bool(r.get("provider")), r.get("provider", "")))
        gates.append(GateResult("ledger_has_freshness", bool(r.get("freshness")), r.get("freshness", "")))
    return gates


def pipeline_ready(gates: list[GateResult]) -> bool:
    core = {
        "run_id_match", "non_fixture", "row_count", "valid_symbol_ratio",
        "valid_price_ratio", "duplicate_ratio", "provenance_hash", "market_date_known",
        "dataset_spot_quotes", "dataset_trading_calendar", "dataset_indices",
        "ledger_appended", "ledger_has_run_id", "ledger_has_provider", "deterministic_tests",
    }
    return all(g.passed for g in gates if g.name in core or (g.severity == "required" and g.name.startswith("ledger_")))


def candidate_data_ready(gates: list[GateResult]) -> bool:
    blocking = {"historical_bars", "major_indices_coverage"}
    if not pipeline_ready(gates):
        return False
    return all(g.passed for g in gates if g.name in blocking)


def run_deterministic_suites() -> dict[str, Any]:
    py = ROOT / ".venv-china-quant" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)
    suites = [
        ("provider-recovery", [str(py), str(ROOT / "scripts/run-provider-recovery-tests.py")]),
        ("paper-ledger", [str(py), str(ROOT / "scripts/run-paper-ledger-tests.py")]),
        ("next-session", [str(py), str(ROOT / "scripts/run-next-session-tests.py")]),
        ("china-quant", [str(py), str(ROOT / "scripts/run-china-quant-tests.py")]),
        ("web-safety", [sys.executable, str(ROOT / "scripts/run-web-safety-tests.py")]),
        ("browser-policy", ["npm", "run", "test:browser-policy"]),
    ]
    results: dict[str, Any] = {}
    failed = []
    for name, cmd in suites:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        ok = r.returncode == 0
        results[name] = {"passed": ok, "tail": (r.stdout or r.stderr)[-400:]}
        if not ok:
            failed.append(name)
    results["multimodal"] = {"passed": None, "note": "optional; Pillow dependency may be absent"}
    results["all_required_passed"] = len(failed) == 0
    results["failed"] = failed
    return results


def append_research_ledger(
    decision: ResearchDecision,
    *,
    base: Path = LEDGER_DIR,
) -> dict[str, Any]:
    """Append NO_TRADE / TRADE_CANDIDATE decision; skip duplicate run_id+target date."""
    from quant.paper_ledger import load_signal_records, signal_ledger_path

    path = signal_ledger_path(base)
    existing = load_signal_records(base)
    for r in existing:
        if (
            r.get("run_id") == decision.run_id
            and r.get("market_data_date") == decision.target_trading_date
            and r.get("status") in ("NO_TRADE", "PLANNED", "zero_candidates")
        ):
            return {"skipped_duplicate": True, "existing_record_id": r.get("record_id")}

    created_at = datetime.now().isoformat(timespec="seconds")
    if decision.decision == "TRADE_CANDIDATE" and decision.candidate:
        c = decision.candidate
        record = {
            "record_id": f"{decision.run_id}:{c['code']}:planned",
            "run_id": decision.run_id,
            "signal_date": decision.analysis_date,
            "market_data_date": decision.target_trading_date,
            "provider": decision.spot_provider,
            "freshness": decision.freshness,
            "symbol": c["code"],
            "name": c.get("name", ""),
            "score": c.get("total_score"),
            "entry_zone": c.get("entry_zone", ""),
            "stop": c.get("stop", ""),
            "target1": c.get("target1", ""),
            "target2": c.get("target2", ""),
            "position_size": c.get("position_size", ""),
            "status": "PLANNED",
            "record_type": "candidate",
            "corrects_record_id": None,
            "created_at": created_at,
            "mode": "PAPER",
            "regime": decision.market_regime,
            "rejection_reasons": [],
        }
    else:
        record = {
            "record_id": f"{decision.run_id}:no-trade",
            "run_id": decision.run_id,
            "signal_date": decision.analysis_date,
            "market_data_date": decision.target_trading_date,
            "provider": decision.spot_provider,
            "freshness": decision.freshness,
            "symbol": "NO_CANDIDATE",
            "name": "",
            "score": None,
            "entry_zone": "",
            "stop": "",
            "target1": "",
            "target2": "",
            "position_size": "0%",
            "status": decision.decision if decision.decision != "TRADE_CANDIDATE" else "NO_TRADE",
            "record_type": "research_decision",
            "corrects_record_id": None,
            "created_at": created_at,
            "mode": "PAPER",
            "rejection_reasons": decision.rejection_reasons,
        }

    base.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"appended": True, "record_id": record["record_id"]}


def run_research(run_id: str, *, skip_tests: bool = False) -> ResearchDecision:
    from quant.data_lake import DATA_ROOT, load_by_run_id

    generated_at = datetime.now().isoformat(timespec="seconds")
    analysis_date = datetime.now().strftime("%Y-%m-%d")

    spot_doc = load_by_run_id("spot_quotes", run_id)
    if not spot_doc:
        return ResearchDecision(
            decision="BLOCKED_BY_PIPELINE",
            run_id=run_id,
            analysis_date=analysis_date,
            data_date="",
            target_trading_date="",
            generated_at=generated_at,
            calendar_provider="",
            spot_provider="",
            rejection_reasons=[f"spot_quotes missing for run_id={run_id}"],
        )

    manifest_path = DATA_ROOT / "manifests" / run_id / "spot_quotes.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    cal_doc = load_by_run_id("trading_calendar", run_id) or {}
    cal_days = cal_doc.get("payload", {}).get("days", [])
    cal_provider = cal_doc.get("provider", "unknown")
    data_date = manifest.get("market_date") or spot_doc.get("market_date") or analysis_date
    latest_mkt = latest_completed_market_date(cal_days, analysis_date) if cal_days else data_date
    target_date = next_open_trading_day(cal_days, latest_mkt) if cal_days else "unknown"

    spot_provider = manifest.get("provider", spot_doc.get("provider", ""))
    freshness = manifest.get("freshness", spot_doc.get("freshness", ""))
    rows = spot_doc.get("payload", {}).get("rows", [])

    gates = verify_snapshot_gates(run_id, spot_doc, manifest)
    gates += verify_supporting_datasets(run_id)
    gates += verify_ledger(run_id)

    test_results = {} if skip_tests else run_deterministic_suites()
    if test_results and not test_results.get("all_required_passed"):
        gates.append(GateResult(
            "deterministic_tests",
            False,
            str(test_results.get("failed")),
        ))

    breadth = compute_breadth(rows)
    idx_doc = load_by_run_id("indices", run_id) or {}
    idx_payload = idx_doc.get("payload", {})
    index_chg = idx_payload.get("sh", {}).get("change_pct")
    available_indices = sum(1 for k in idx_payload if k not in ("source_dataset", "endpoint"))

    regime, regime_score, regime_conf, supporting, opposing = classify_regime_label(
        breadth, index_chg, available_indices=available_indices,
    )

    decision = ResearchDecision(
        decision="NO_TRADE",
        run_id=run_id,
        analysis_date=analysis_date,
        data_date=data_date,
        target_trading_date=target_date,
        generated_at=generated_at,
        calendar_provider=cal_provider,
        spot_provider=spot_provider,
        row_count=len(rows),
        quality_status="passed" if all(
            g.passed for g in gates
            if g.name in ("row_count", "valid_symbol_ratio", "valid_price_ratio", "duplicate_ratio", "provenance_hash", "non_fixture")
        ) else "failed",
        freshness=freshness,
        market_regime=regime,
        regime_score=regime_score,
        regime_confidence=regime_conf,
        breadth=asdict(breadth),
        gates=[asdict(g) for g in gates],
        limitations=[
            "Fundamental, valuation, and official disclosure feeds not persisted for this run_id",
            "Per-stock 60-day bar history not persisted — universe-wide bar gate fails",
            f"Major index coverage incomplete ({available_indices} benchmark(s))",
        ],
    )

    if not pipeline_ready(gates):
        decision.decision = "BLOCKED_BY_PIPELINE"
        decision.rejection_reasons = [f"{g.name}: {g.detail}" for g in gates if not g.passed and g.name in {
            "run_id_match", "non_fixture", "row_count", "valid_symbol_ratio", "valid_price_ratio",
            "duplicate_ratio", "provenance_hash", "market_date_known", "ledger_appended", "deterministic_tests",
        }]
        decision.ledger_result = append_research_ledger(decision)
        return decision

    if not candidate_data_ready(gates):
        decision.decision = "BLOCKED_BY_DATA"
        decision.rejection_reasons = [
            g.detail for g in gates
            if not g.passed and g.name in (
                "historical_bars", "major_indices_coverage",
                "dataset_spot_quotes", "dataset_trading_calendar", "dataset_indices",
            )
        ]
        if regime in ("RISK_OFF", "DISORDERED"):
            decision.rejection_reasons.append(f"Regime {regime} defaults to NO_TRADE")
        decision.ledger_result = append_research_ledger(decision)
        return decision

    if regime in ("RISK_OFF", "DISORDERED"):
        decision.decision = "NO_TRADE"
        decision.rejection_reasons = [f"Regime {regime} — policy default NO_TRADE", *opposing]
    else:
        decision.decision = "NO_TRADE"
        decision.rejection_reasons = [
            "No stock passed all gates with complete bars, fundamentals, and disclosures",
            "Universe screening requires persisted historical bars (UNAVAILABLE)",
        ]

    decision.ledger_result = append_research_ledger(decision)
    return decision


def write_reports(decision: ResearchDecision, test_results: dict[str, Any]) -> dict[str, Path]:
    base = LEDGER_DIR
    base.mkdir(parents=True, exist_ok=True)

    system_ready = pipeline_ready([GateResult(**g) for g in decision.gates]) and decision.quality_status == "passed"
    candidate_ready = candidate_data_ready([GateResult(**g) for g in decision.gates])

    ready = {
        "generated_at": decision.generated_at,
        "run_id": decision.run_id,
        "branch": "chore/cursor-operating-system",
        "pipeline_verified": system_ready,
        "system_ready_for_daily_paper_research": system_ready and candidate_ready,
        "verdict": "SYSTEM_READY_FOR_DAILY_PAPER_RESEARCH" if (system_ready and candidate_ready) else "PIPELINE_VERIFIED_WITH_DATA_GAPS",
        "gates": decision.gates,
        "test_results": test_results,
        "ledger_verified": any(g["name"] == "ledger_appended" and g["passed"] for g in decision.gates),
    }
    ready_path = base / "SYSTEM_READY_CHECK.json"
    ready_path.write_text(json.dumps(ready, ensure_ascii=False, indent=2), encoding="utf-8")

    ready_md = [
        "# System Ready Check",
        "",
        f"**Generated**: {decision.generated_at}",
        f"**run_id**: `{decision.run_id}`",
        "",
        f"## Verdict: `{ready['verdict']}`",
        "",
        f"- Pipeline verified: **{system_ready}**",
        f"- Candidate data ready: **{candidate_ready}**",
        f"- Spot provider: **{decision.spot_provider}** ({decision.row_count} rows)",
        "",
        "## Gates",
        "",
    ]
    for g in decision.gates:
        mark = "PASS" if g["passed"] else "FAIL"
        ready_md.append(f"- [{mark}] {g['name']}: {g['detail']}")
    (base / "SYSTEM_READY_CHECK.md").write_text("\n".join(ready_md), encoding="utf-8")

    cand = decision.to_dict()
    cand["disclaimer"] = "Internal quantitative research and paper-trading output. Not a guarantee of return. No real order has been placed."
    (base / "NEXT_TRADING_DAY_RESEARCH_CANDIDATE.json").write_text(
        json.dumps(cand, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    cand_md = [
        f"# Next Trading Day Research Candidate",
        "",
        f"## Decision: **{decision.decision}**",
        "",
        "### Timing",
        f"- Data date: {decision.data_date}",
        f"- Analysis generated at: {decision.generated_at}",
        f"- Target trading date: {decision.target_trading_date}",
        f"- Calendar provider: {decision.calendar_provider}",
        "",
        "### Data provenance",
        f"- run_id: `{decision.run_id}`",
        f"- spot provider: {decision.spot_provider}",
        f"- freshness: {decision.freshness}",
        f"- row count: {decision.row_count}",
        f"- quality: {decision.quality_status}",
        "",
        "### Market regime",
        f"- classification: {decision.market_regime}",
        f"- score: {decision.regime_score:.1f}",
        f"- confidence: {decision.regime_confidence}",
        "",
        "### Rejection reasons" if decision.rejection_reasons else "",
    ]
    if decision.rejection_reasons:
        cand_md += [f"- {r}" for r in decision.rejection_reasons]
    cand_md += ["", "### Disclaimer", "", cand["disclaimer"]]
    (base / "NEXT_TRADING_DAY_RESEARCH_CANDIDATE.md").write_text("\n".join(cand_md), encoding="utf-8")

    exec_report = {
        "system_readiness": ready["verdict"],
        "run_id": decision.run_id,
        "data_date": decision.data_date,
        "target_trading_date": decision.target_trading_date,
        "selected_provider": decision.spot_provider,
        "row_count": decision.row_count,
        "quality_result": decision.quality_status,
        "market_regime": decision.market_regime,
        "candidate_decision": decision.decision,
        "ledger_append": decision.ledger_result,
        "limitations": decision.limitations,
    }
    (base / "NEXT_SESSION_EXECUTION_REPORT.json").write_text(
        json.dumps(exec_report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    exec_md = "\n".join([
        "# Next Session Execution Report",
        "",
        f"**Decision**: {decision.decision}",
        f"**run_id**: `{decision.run_id}`",
        f"**Target session**: {decision.target_trading_date}",
        f"**Provider**: {decision.spot_provider} ({decision.row_count} rows)",
        f"**Regime**: {decision.market_regime}",
        "",
        "## Limitations",
        *[f"- {x}" for x in decision.limitations],
    ])
    (base / "NEXT_SESSION_EXECUTION_REPORT.md").write_text(exec_md, encoding="utf-8")

    return {
        "system_ready": base / "SYSTEM_READY_CHECK.md",
        "candidate": base / "NEXT_TRADING_DAY_RESEARCH_CANDIDATE.md",
        "execution": base / "NEXT_SESSION_EXECUTION_REPORT.md",
    }
