#!/usr/bin/env python3
"""End-to-end daily quant pipeline per essential spec."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PY = ROOT / ".venv-china-quant" / "bin" / "python"
LEDGER = ROOT / "docs" / "ai" / "daily-trading"


def _run(cmd: list[str]) -> dict:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {"cmd": " ".join(cmd), "ok": r.returncode == 0, "code": r.returncode, "tail": (r.stdout + r.stderr)[-1500:]}


def main() -> int:
    from quant.run_context import new_run_id, set_run_id
    from quant.composite_provider import CompositeMarketDataProvider
    from quant.data_lake import save_snapshot
    from quant.candidate_data_gate import evaluate_candidate_readiness
    from quant.daily_quant_report import generate_daily_report, write_daily_report
    from quant.rag_memory import append_run_summary, ensure_memory_layout, index_report_doc
    from quant.live_test_scheduler import schedule_live_test
    from quant.backfill import update_indices, update_daily_bars, update_sectors, update_fundamentals, update_disclosures
    from quant.features_compute import build_feature_store
    from quant.warehouse import sync_from_partitions
    from tools.china_quant.regime_v2 import classify_regime_v2

    pre = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    # Tests first
    tr = _run([str(PY), str(ROOT / "scripts/run-all-readiness-tests.py")])

    # Backfill
    idx_rep = update_indices(min_bars=250)
    bar_rep = update_daily_bars(target_days=120, max_new=80)
    sec_rep = update_sectors()
    fund_rep = update_fundamentals()
    disc_rep = update_disclosures()
    sync_from_partitions()
    feat_rep = build_feature_store()

    run_id = new_run_id()
    set_run_id(run_id)
    composite = CompositeMarketDataProvider()
    snap = composite.fetch_market_snapshot(
        datasets=["spot_quotes", "trading_calendar", "indices"],
        live_only=False,
        route_mode="latest_available",
    )
    spot = snap.get("spot_quotes")
    winner = spot.result if spot and spot.result else None
    if not winner or not winner.ok:
        print(json.dumps({"error": "spot fetch failed", "run_id": run_id}, indent=2))
        return 2

    payload = winner.payload if isinstance(winner.payload, dict) else {}
    save_snapshot(
        "spot_quotes", run_id=run_id,
        raw_payload=payload, normalized_payload=payload,
        provider=winner.provider,
        provenance={"freshness": winner.freshness, "is_live": winner.is_live},
    )

    rows = payload.get("rows", [])
    indices_payload = {}
    if snap.get("indices") and snap["indices"].result:
        indices_payload = snap["indices"].result.payload or {}

    from quant.indices_store import load_index_summary, INDEX_ROOT
    index_hist = []
    p = INDEX_ROOT / "000001_SH.json"
    if p.exists():
        index_hist = json.loads(p.read_text()).get("bars", [])

    regime = classify_regime_v2(indices_payload, rows, index_hist=index_hist)
    readiness = evaluate_candidate_readiness(
        run_id=run_id, spot_row_count=len(rows),
        spot_provider=winner.provider, quality_passed=True,
    )

    report = generate_daily_report(
        run_id=run_id, spot_payload=payload,
        provider=winner.provider, freshness=winner.freshness or "",
        market_date=winner.market_date or payload.get("market_date", ""),
        readiness=readiness.to_dict(), regime_analysis=regime,
    )
    paths = write_daily_report(report)

    # Paper ledger
    ledger_result = {}
    try:
        from quant.paper_ledger import append_research_decision
        ledger_result = append_research_decision(
            LEDGER,
            run_id=run_id,
            decision=report.decision,
            market_data_date=report.data_cutoff,
            provider=winner.provider,
            freshness=winner.freshness or "",
            regime=report.regime,
            reasons=report.no_trade_reasons,
            candidate=report.candidate,
        )
    except Exception as e:
        ledger_result = {"error": str(e)}

    blockers = readiness.rejection_reasons if not readiness.ready else []
    mem = ensure_memory_layout(blockers=blockers)
    append_run_summary(run_id=run_id, summary={
        "decision": report.decision, "maturity": readiness.maturity,
        "report": paths.get("json"), "ledger": ledger_result,
    })
    index_report_doc(Path(paths["md"]))

    live_sched = schedule_live_test(dry_run=False)

    final = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pre_change_commit": pre,
        "run_id": run_id,
        "tests": tr,
        "backfill": {"indices": idx_rep, "daily_bars": bar_rep, "sectors": sec_rep,
                     "fundamentals": fund_rep, "disclosures": disc_rep, "features": feat_rep},
        "readiness": readiness.to_dict(),
        "daily_report": paths,
        "decision": report.decision,
        "live_test_schedule": live_sched,
        "memory": mem,
        "maturity": readiness.maturity,
    }
    (LEDGER / "FINAL_DAILY_REPORT_DEPLOYMENT.json").write_text(json.dumps(final, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (LEDGER / "FINAL_DAILY_REPORT_DEPLOYMENT.md").write_text(
        f"# FINAL_DAILY_REPORT_DEPLOYMENT\n\nDecision: {report.decision}\nMaturity: {readiness.maturity}\nRun: {run_id}\n",
        encoding="utf-8",
    )
    print(json.dumps({"run_id": run_id, "decision": report.decision, "maturity": readiness.maturity, "tests_ok": tr["ok"]}, indent=2))
    return 0 if tr["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
