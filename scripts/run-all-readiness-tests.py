#!/usr/bin/env python3
"""Unified readiness test runner with failure classification."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "ai" / "daily-trading"
PY = ROOT / ".venv-china-quant" / "bin" / "python"
if not PY.exists():
    PY = Path(sys.executable)

SUITES = [
    ("provider-recovery", "run-provider-recovery-tests.py", "DETERMINISTIC_INTEGRATION"),
    ("paper-ledger", "run-paper-ledger-tests.py", "DETERMINISTIC_INTEGRATION"),
    ("next-session", "run-next-session-tests.py", "DETERMINISTIC_INTEGRATION"),
    ("multiprovider-v2", "run-multiprovider-v2-tests.py", "DETERMINISTIC_INTEGRATION"),
    ("china-quant", "run-china-quant-tests.py", "UNIT"),
    ("china-quant-full", "run-china-quant-full-tests.py", "UNIT"),
    ("web-safety", "run-web-safety-tests.py", "UNIT"),
    ("multimodal", "run-multimodal-tests.py", "UNIT"),
    ("browser-policy", None, "DETERMINISTIC_INTEGRATION"),
    ("gateway-v2", "run-gateway-tests.py", "DETERMINISTIC_INTEGRATION"),
]


def _classify(name: str, rc: int, output: str) -> str:
    o = output.lower()
    if rc == 0:
        return "PASS"
    if "modulenotfounderror" in o or "no module named" in o:
        return "DEPENDENCY_MISSING"
    if "permission" in o or "not_configured" in o or "token" in o:
        return "PERMISSION_UNAVAILABLE"
    if "connection" in o or "network" in o or "remote" in o:
        return "NETWORK_BLOCKED"
    if "outside session" in o or "market closed" in o:
        return "LIVE_TEST_OUTSIDE_SESSION"
    if "assert" in o or "traceback" in o:
        return "CODE_DEFECT"
    return "CODE_DEFECT"


def _run_suite(name: str, script: str | None) -> dict:
    if script:
        r = subprocess.run([str(PY), str(ROOT / "scripts" / script)], cwd=ROOT, capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        print(out)
        return {
            "name": name,
            "passed": r.returncode == 0,
            "exit_code": r.returncode,
            "classification": _classify(name, r.returncode, out),
            "output_tail": out[-2000:],
        }
    r = subprocess.run(["npm", "run", "test:browser-policy"], cwd=ROOT, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    print(out)
    return {
        "name": name,
        "passed": r.returncode == 0,
        "exit_code": r.returncode,
        "classification": _classify(name, r.returncode, out),
        "output_tail": out[-2000:],
    }


def main() -> int:
    results = []
    for name, script, category in SUITES:
        print(f"\n=== {name} ({category}) ===")
        row = _run_suite(name, script)
        row["category"] = category
        results.append(row)

    passed = [r for r in results if r["passed"]]
    failed = [r for r in results if not r["passed"]]
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "suites": results,
        "passed_count": len(passed),
        "failed_count": len(failed),
        "all_deterministic_passed": all(
            r["passed"] for r in results if r["category"] in ("UNIT", "DETERMINISTIC_INTEGRATION")
        ),
        "resolved_failures": [],
        "remaining_failures": [r["name"] for r in failed],
    }
    LEDGER.mkdir(parents=True, exist_ok=True)
    (LEDGER / "TEST_RECOVERY_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    lines = [
        "# TEST_RECOVERY_REPORT",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"**Passed:** {len(passed)}/{len(results)}",
        f"**All deterministic:** {report['all_deterministic_passed']}",
        "",
    ]
    for r in results:
        lines.append(f"- {r['name']}: {'PASS' if r['passed'] else r['classification']}")
    (LEDGER / "TEST_RECOVERY_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSUMMARY passed={len(passed)} failed={len(failed)}")
    return 0 if report["all_deterministic_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
