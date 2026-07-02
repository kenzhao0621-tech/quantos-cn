#!/usr/bin/env python
"""Phase 1 DataOS quality gate — wraps quant.dataos checks and view coverage.

Usage:
    python scripts/check_data_quality.py --mode quick
    python scripts/check_data_quality.py --mode full

Writes artifacts/reports/data_quality_<ts>.json and prints a summary.
Exit code 0 = passed, 1 = warnings, 2 = blocked (warehouse missing).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def view_coverage() -> dict:
    from quant.warehouse import query

    out: dict = {}
    for view, key_sql in (
        ("daily_bars", "SELECT COUNT(*) AS n, COUNT(DISTINCT trade_date) AS d, MIN(trade_date) AS lo, MAX(trade_date) AS hi FROM daily_bars"),
        ("index_bars", "SELECT COUNT(*) AS n, COUNT(DISTINCT trade_date) AS d, MIN(trade_date) AS lo, MAX(trade_date) AS hi FROM index_bars"),
        ("features", "SELECT COUNT(*) AS n, COUNT(DISTINCT trade_date) AS d, MIN(trade_date) AS lo, MAX(trade_date) AS hi FROM features"),
        ("adj_factors", "SELECT COUNT(*) AS n, COUNT(DISTINCT trade_date) AS d, MIN(trade_date) AS lo, MAX(trade_date) AS hi FROM adj_factors"),
        ("industry_map", "SELECT COUNT(*) AS n, COUNT(DISTINCT sector_name) AS d, NULL AS lo, NULL AS hi FROM industry_map"),
        ("fundamental", "SELECT COUNT(*) AS n, COUNT(DISTINCT trade_date) AS d, MIN(trade_date) AS lo, MAX(trade_date) AS hi FROM fundamental"),
        ("disclosures", "SELECT COUNT(*) AS n, NULL AS d, NULL AS lo, NULL AS hi FROM disclosures"),
    ):
        try:
            row = query(key_sql)[0]
            out[view] = {
                "rows": int(row.get("n") or 0),
                "distinct": int(row["d"]) if row.get("d") is not None else None,
                "min": str(row["lo"]) if row.get("lo") is not None else None,
                "max": str(row["hi"]) if row.get("hi") is not None else None,
                "present": int(row.get("n") or 0) > 0,
            }
        except Exception as exc:
            out[view] = {"rows": 0, "present": False, "error": str(exc)[:100]}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["quick", "full"], default="quick")
    args = parser.parse_args()

    from quant.dataos.quality_checker import run_warehouse_quality_checks

    report: dict = {
        "mode": args.mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "warehouse_checks": run_warehouse_quality_checks(),
        "view_coverage": view_coverage(),
    }

    if args.mode == "full":
        try:
            from quant.dataos.drift_detector import run_drift_checks  # type: ignore[attr-defined]

            report["drift"] = run_drift_checks()
        except Exception as exc:
            report["drift"] = {"status": "SKIPPED", "reason": str(exc)[:100]}
        try:
            from quant.dataos.corporate_action_checker import run_corporate_action_checks  # type: ignore[attr-defined]

            report["corporate_actions"] = run_corporate_action_checks()
        except Exception as exc:
            report["corporate_actions"] = {"status": "SKIPPED", "reason": str(exc)[:100]}

    cov = report["view_coverage"]
    degraded = [v for v, meta in cov.items() if not meta.get("present")]
    report["degraded_views"] = degraded
    wh = report["warehouse_checks"]
    if not wh.get("warehouse_exists"):
        report["verdict"] = "BLOCKED"
        code = 2
    elif wh.get("passed") and not degraded:
        report["verdict"] = "OK"
        code = 0
    else:
        report["verdict"] = "WARN"
        code = 1

    out_dir = ROOT / "artifacts" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"data_quality_{ts}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"verdict={report['verdict']} mode={args.mode}")
    print(f"daily_bars: {cov['daily_bars']}")
    if degraded:
        print(f"degraded_views: {degraded}")
    for c in wh.get("checks", []):
        mark = "PASS" if c.get("passed") else "FAIL"
        print(f"  [{mark}] {c['name']}")
    print(f"report: {out_path.relative_to(ROOT)}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
