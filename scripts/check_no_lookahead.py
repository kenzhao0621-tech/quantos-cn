#!/usr/bin/env python
"""Phase 2 FeatureOS gate — real lookahead/leakage audit.

Replaces the synthetic leakage stub in run_quantos_audit.py with the real
quant.validation.leakage_detector audit. Writes artifacts/leakage_report.json.

Usage: python scripts/check_no_lookahead.py [--as-of YYYY-MM-DD]
Exit code 0 = passed, 1 = failed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", dest="as_of", default=None)
    args = parser.parse_args()

    from quant.validation.leakage_detector import persist_leakage_report, run_leakage_audit

    report = run_leakage_audit(as_of_date=args.as_of)
    path = persist_leakage_report(report)

    print(f"passed={report['passed']}")
    for c in report["checks"]:
        mark = "PASS" if c.get("passed") else "FAIL"
        note = c.get("note") or c.get("detail") or ""
        print(f"  [{mark}] {c['name']}" + (f" — {note}" if note else ""))
    print(f"report: {path.relative_to(ROOT)}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
