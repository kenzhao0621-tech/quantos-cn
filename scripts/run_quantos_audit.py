#!/usr/bin/env python3
"""Task 1 — QuantOS architecture audit (no scoring changes)."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ART = ROOT / "artifacts"
ART.mkdir(parents=True, exist_ok=True)


def main() -> int:
    from quant.quantos.phase_a_audit import run_phase_a_audit
    from quant.quantos.alpha158_audit import run_alpha158_audit
    from quant.quantos.registry_report import write_factor_artifacts

    ts = datetime.now().isoformat(timespec="seconds")
    audit = run_phase_a_audit()
    alpha = run_alpha158_audit()
    factor_art = write_factor_artifacts()

    mapping = _build_module_mapping()
    missing = _build_missing_modules()
    debt = _build_technical_debt()
    risks = _build_reliability_risks()

    (ART / "module_mapping.json").write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")
    (ART / "missing_modules.json").write_text(json.dumps(missing, indent=2, ensure_ascii=False), encoding="utf-8")
    (ART / "technical_debt_report.md").write_text(debt, encoding="utf-8")
    (ART / "reliability_risk_report.md").write_text(risks, encoding="utf-8")
    _write_architecture_md(ts, audit, mapping, missing)

    print(json.dumps({
        "ok": True,
        "artifacts": [
            "quantos_architecture_audit.md",
            "module_mapping.json",
            "missing_modules.json",
            "technical_debt_report.md",
            "reliability_risk_report.md",
            "alpha158_audit_report.md",
            "factor_conflict_report.md",
            "factor_registry.yaml",
            "factor_validation_report.json",
        ],
    }, indent=2))
    return 0


def _build_module_mapping() -> dict:
    modules = [
        "DataOS", "ResearchOS", "EventOS", "ValidationOS", "PortfolioOS",
        "ExecutionOS", "RiskOS", "ExplainabilityOS", "LearningOS", "UserOS", "SimulationOS",
    ]
    spec_files = {
        "DataOS": ["quant/dataos/quality_checker.py", "quant/dataos/drift_detector.py", "quant/dataos/corporate_action_checker.py"],
        "ResearchOS": ["configs/factor_registry.yaml", "quant/features/alpha158.py", "quant/features/neutralization.py", "quant/features/factor_library.py"],
        "EventOS": ["quant/event/event_classifier.py", "quant/event/event_graph.py", "quant/disclosures/pit_filter.py"],
        "ValidationOS": ["quant/validation/purged_kfold.py", "quant/validation/walk_forward.py", "quant/validation/leakage_detector.py"],
        "PortfolioOS": ["quant/portfolio/optimizer.py", "quant/portfolio/constraints.py", "quant/portfolio/cost_model.py"],
        "ExecutionOS": ["gateway/paper/engine.py", "quant/tradability/mask.py", "quant/execution/a_share_rules.py"],
        "RiskOS": ["gateway/risk/engine.py", "gateway/risk/kill_switch.py", "quant/risk/exposure_report.py"],
        "ExplainabilityOS": ["quant/explain/factor_contribution.py", "quant/explain/bucket_stats.py", "quant/scoring/enrichment.py"],
        "LearningOS": ["quant/learning/daily_audit.py", "quant/learning/factor_decay.py", "quant/dataos/drift_detector.py"],
        "UserOS": ["apps/portal-web/index.html", "apps/portal-web/app.js", "gateway/api/bff_market.py"],
        "SimulationOS": ["quant/simulation/state_engine.py", "quant/simulation/feature_generator.py", "quant/simulation/counterfactual.py"],
    }
    out = {}
    for m in modules:
        files = spec_files.get(m, [])
        existing = [f for f in files if (ROOT / f).exists()]
        missing = [f for f in files if not (ROOT / f).exists()]
        if len(existing) == len(files):
            status = "done"
        elif existing:
            status = "partial"
        else:
            status = "missing"
        out[m] = {"existing_files": existing, "missing_files": missing, "status": status}
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "modules": out}


def _build_missing_modules() -> dict:
    mapping = _build_module_mapping()
    gaps = []
    for name, info in mapping["modules"].items():
        if info["missing_files"]:
            gaps.append({"module": name, "missing_files": info["missing_files"], "status": info["status"]})
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "gaps": gaps}


def _build_technical_debt() -> str:
    return """# QuantOS Technical Debt Report

## P0 — Correctness / leakage
1. **Disclosure PIT bypass** — `screener_service._load_disclosure_map()` loads all rows without `pit_filter`.
2. **Label semantics split** — `labels.py` T+1 entry vs `model_validation_service` same-day close.
3. **Leakage test stub** — pipeline `_leakage_check()` is synthetic; real detector required.
4. **Fundamentals without as_of** — `_load_fundamental_map()` uses latest snapshot only.

## P1 — Architecture
5. **Four weight systems** — PRESETS, alpha_blend, baseline.py (orphaned), ensemble.
6. **screen() / _score_universe() duplication** — ~150 lines duplicated.
7. **Three portfolio paths** — optimizer, allocator, gateway/portfolio/constructor.
8. **factor_registry.yaml not loaded at runtime** — documentation only.

## P2 — Alpha158 (retained, not downgraded)
9. **ROC formula differs from textbook** — documented in `factor_conflict_report.md`; **retain existing**.
10. **Three naming layers** — full Alpha158 (ML), price_momentum_lite (screener blend), qlib alpha158_lite (4 cols).

## P3 — Operations
11. Module-level `_LIVE_CACHE` in screener.
12. Artifacts cache reuse in upgrade pipeline.
13. LearningOS outcome_tracker label mismatch.

## Recommended order
PIT disclosures → leakage_detector → unify labels → registry loader → dedupe screener paths.
"""


def _build_reliability_risks() -> str:
    return """# QuantOS Reliability Risk Report

| Risk | Severity | Location | Mitigation |
|------|----------|----------|------------|
| Future announcement leakage | HIGH | screener disclosure map | Wire `pit_filter.filter_point_in_time` |
| Same-day vs T+1 label mismatch | HIGH | validation vs labels.py | Align proof returns to T+1 |
| Survivorship (ST filter post-hoc) | MEDIUM | screener SQL | Document + optional delist table |
| Unadjusted prices | MEDIUM | alpha158, screener | corporate_action_checker PARTIAL |
| Data drift | MEDIUM | drift_detector | disable_live_trading gate |
| ML overfit (23 OOS days) | MEDIUM | model_metrics.json | Keep CANDIDATE status |
| Top-N without portfolio constraints in UI | MEDIUM | allocator vs optimizer | Wire optimize_topk to API |
| Kill switch not auto on validation fail | LOW | kill_switch | LearningOS daily_audit hook |

**Backtest risk:** Negative OOS Sharpe in rolling window — do not promote to production.
**风控 risk:** Kill switch manual reset only — correct for safety.
**数据风险:** Warehouse OK; drift detected on vol_20 — monitor daily.
"""


def _write_architecture_md(ts: str, audit: dict, mapping: dict, missing: dict) -> None:
    lines = [
        "# QuantOS Architecture Audit",
        "",
        f"Generated: {ts}",
        "",
        "## Current architecture",
        "",
        "```text",
        "Portal (apps/portal-web) → Gateway (FastAPI) → quant/application → DuckDB + Parquet",
        "Paper/Risk: gateway/paper + gateway/risk",
        "ML: quant/models + data/parquet/features/alpha158/",
        "```",
        "",
        "## OS module status",
        "",
    ]
    for name, info in mapping["modules"].items():
        lines.append(f"- **{name}**: {info['status']} ({len(info['existing_files'])} files)")
    lines.extend([
        "",
        "## Data flow",
        "1. `daily_bars` (DuckDB) → screener factors + Alpha158 cache",
        "2. Z-score + industry/size neutralization → baseline_score",
        "3. ML gate → ensemble (45/35/20) or baseline fallback",
        "4. enrich_candidate → portal cards",
        "5. paper engine → T+1 execution simulation",
        "",
        "## Alpha158 policy",
        "**Do not downgrade.** Full 158-column `alpha158_compatible_v1` is production ML feature set.",
        "Screener blend uses `price_momentum_lite` separately — not a replacement.",
        "",
        "## Entry points",
        "- `make app` — portal + gateway",
        "- `python scripts/run_quantos_audit.py` — this audit",
        "- `python scripts/run_quantos_closed_loop.py` — closed loop gates",
        "- `pytest tests/` — unit tests",
    ])
    (ART / "quantos_architecture_audit.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
