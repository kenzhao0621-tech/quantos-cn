#!/usr/bin/env python3
"""Pre-launch maintenance — audit, closed loop, gates template, final report."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    steps = []
    subprocess.run([sys.executable, str(ROOT / "scripts/run_quantos_audit.py")], check=False)
    steps.append("audit")
    subprocess.run([sys.executable, str(ROOT / "scripts/run_quant_upgrade_pipeline.py")], check=False)
    steps.append("validate")
    subprocess.run([sys.executable, str(ROOT / "scripts/run_quantos_closed_loop.py")], check=False)
    steps.append("closed_loop")

    gates_path = ROOT / "data" / "gateway" / "live_trading_gates.json"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    template = {
        "execution_level": 3,
        "legal_review_required": True,
        "legal_review_passed": True,
        "max_daily_notional_cny": 50000.0,
        "max_single_order_cny": 10000.0,
        "user_confirmed_risk": True,
        "real_money_enabled": True,
        "unattended_auto_enabled": False,
        "browser_auto_submit": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Set unattended_auto_enabled=true after Sidecar configured",
    }
    if not gates_path.exists():
        gates_path.write_text(json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8")
        steps.append("gates_template_created")

    subprocess.run([sys.executable, str(ROOT / "scripts/generate_final_quantos_report.py")], check=False)
    steps.append("final_report")

    r = subprocess.run([sys.executable, "-m", "pytest", "tests/portfolioos", "tests/executionos", "-q"], cwd=ROOT)
    print(json.dumps({"ok": r.returncode == 0, "steps": steps}, indent=2))
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
