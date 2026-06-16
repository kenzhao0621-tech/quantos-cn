#!/usr/bin/env python3
"""V4 deterministic test runner — all suites, no live required."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv-china-quant" / "bin" / "python"
if not PY.exists():
    PY = Path(sys.executable)

SUITES = [
    ("provider-recovery", [str(PY), str(ROOT / "scripts/run-provider-recovery-tests.py")]),
    ("paper-ledger", [str(PY), str(ROOT / "scripts/run-paper-ledger-tests.py")]),
    ("next-session", [str(PY), str(ROOT / "scripts/run-next-session-tests.py")]),
    ("multiprovider-v2", [str(PY), str(ROOT / "scripts/run-multiprovider-v2-tests.py")]),
    ("china-quant", [str(PY), str(ROOT / "scripts/run-china-quant-tests.py")]),
    ("china-quant-full", [str(PY), str(ROOT / "scripts/run-china-quant-full-tests.py")]),
    ("china-quant-real", [str(PY), str(ROOT / "scripts/run-china-quant-real-tests.py")]),
    ("web-safety", [sys.executable, str(ROOT / "scripts/run-web-safety-tests.py")]),
    ("multimodal", [sys.executable, str(ROOT / "scripts/run-multimodal-tests.py")]),
    ("browser-policy", ["npm", "run", "test:browser-policy"]),
]

failed = []
for name, cmd in SUITES:
    print(f"\n=== {name} ===")
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        failed.append(name)
    else:
        print(f"PASS {name}")

print(f"\nV4 SUMMARY failed={failed or 'none'}")
sys.exit(1 if failed else 0)
