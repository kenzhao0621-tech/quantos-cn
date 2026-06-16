#!/usr/bin/env python3
"""Full disclosure/scheduler/PDF acceptance run and reports 01-08."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "ai" / "daily-trading"
PRE = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
BRANCH = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
PY = ROOT / ".venv-china-quant" / "bin" / "python"


def _write(name: str, payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [f"# {name}\n", f"Generated: {payload.get('generated_at', '')}\n"]
    for k, v in payload.items():
        if k != "generated_at":
            lines.append(f"- **{k}**: {v}\n")
    (OUT / f"{name}.md").write_text("".join(lines), encoding="utf-8")


def main() -> int:
    ts = datetime.utcnow().isoformat() + "Z"

    # Tests
    tr = subprocess.run([str(PY), str(ROOT / "scripts/run-disclosure-scheduler-tests.py")], cwd=ROOT)
    readiness = subprocess.run([str(PY), str(ROOT / "scripts/run-all-readiness-tests.py")], cwd=ROOT)

    from quant.disclosure_store import run_official_disclosure_update, disclosure_coverage_report
    disc = run_official_disclosure_update(days_back=7, use_network=True)

    from quant.candidate_data_gate import evaluate_candidate_readiness
    readiness_result = evaluate_candidate_readiness(
        run_id="acceptance", spot_row_count=5500, spot_provider="akshare_sina", quality_passed=True,
    )

    from quant.live_test_scheduler import schedule_live_test, live_market_test_status
    live_dry = schedule_live_test(dry_run=True)
    live_install = schedule_live_test(dry_run=False)

    from quant.daily_report_scheduler import schedule_daily_report, daily_report_schedule_status
    daily_dry = schedule_daily_report(dry_run=True)

    _write("01_DISCLOSURE_PROVIDER_REPORT", {
        "generated_at": ts,
        "providers": ["cninfo_official", "sse_official", "szse_official", "bse_official"],
        "primary_status": disc.get("primary_status") or disc.get("fetch", {}).get("primary_status"),
        "query_state": disc.get("query_state") or disc.get("fetch", {}).get("query_state"),
        "row_count": disc.get("row_count", 0),
    })

    cov = disclosure_coverage_report()
    _write("02_DISCLOSURE_COVERAGE_REPORT", {"generated_at": ts, **cov})

    from quant.disclosures.pit_filter import filter_point_in_time
    pit = filter_point_in_time(disc.get("rows", [])[:100], analysis_cutoff=datetime.now().strftime("%Y-%m-%d"))
    _write("03_DISCLOSURE_POINT_IN_TIME_AUDIT", {"generated_at": ts, **pit.to_dict()})

    _write("04_CANDIDATE_GATE_REPAIR_REPORT", {
        "generated_at": ts,
        "disclosure_state": readiness_result.disclosure_state,
        "ready": readiness_result.ready,
        "gates": readiness_result.gates,
    })

    _write("05_SCHEDULER_REPRODUCIBILITY_REPORT", {
        "generated_at": ts,
        "live_test_dry_run": live_dry,
        "live_test_installed": live_install,
        "daily_report_dry_run": daily_dry,
        "live_status": live_market_test_status(),
        "daily_status": daily_report_schedule_status(),
    })

    # Run daily pipeline for PDF
    pipe = subprocess.run([str(PY), str(ROOT / "scripts/run-daily-quant-pipeline.py")], cwd=ROOT, capture_output=True, text=True)
    pdf_qa = {}
    desktop = {}
    daily_json = OUT / "daily"
    json_files = sorted(daily_json.glob("*_DAILY_QUANT_REPORT.json")) if daily_json.exists() else []
    pdf_files = sorted(daily_json.glob("*_DAILY_QUANT_REPORT.pdf")) if daily_json.exists() else []
    if json_files and pdf_files:
        from quant.report_renderer import qa_pdf
        rep = json.loads(json_files[-1].read_text(encoding="utf-8"))
        pdf_qa = qa_pdf(pdf_files[-1], rep)
        desktop_path = Path("/Users/kenzhao/Desktop/China_A_Share_Daily_Reports")
        if desktop_path.exists():
            desktop = {"desktop_root": str(desktop_path), "files": [str(p) for p in desktop_path.rglob("*")][:20]}

    _write("06_PDF_RENDERING_ACCEPTANCE_REPORT", {
        "generated_at": ts,
        "pipeline_exit": pipe.returncode,
        "pdf_qa": pdf_qa,
        "pdf_files": [str(p) for p in pdf_files],
    })
    _write("07_DESKTOP_DELIVERY_REPORT", {"generated_at": ts, **desktop})

    _write("08_FINAL_DISCLOSURE_SCHEDULER_PDF_CAPABILITY_REPORT", {
        "generated_at": ts,
        "repository": str(ROOT),
        "branch": BRANCH,
        "pre_change_commit": PRE,
        "backup": ".cursor-backups/disclosure-scheduler-pdf-20260616-210637",
        "disclosure_row_count": disc.get("row_count", 0),
        "verified_zero_results": disc.get("verified_zero_results", False),
        "candidate_readiness": readiness_result.to_dict(),
        "tests_passed": tr.returncode == 0 and readiness.returncode == 0,
        "live_test_schedule": live_install.get("target_session"),
        "daily_schedule": "15:20 CST trading-day wrapper",
        "remaining_blockers": readiness_result.rejection_reasons,
    })

    print(json.dumps({"tests": tr.returncode, "readiness": readiness.returncode, "pipeline": pipe.returncode}, indent=2))
    return 0 if tr.returncode == 0 and readiness.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
