#!/usr/bin/env python3
"""Final QuantOS upgrade report — Spec §17."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"


def main() -> int:
    mapping = json.loads((ART / "module_mapping.json").read_text()) if (ART / "module_mapping.json").exists() else {}
    closed = json.loads((ART / "QUANTOS_CLOSED_LOOP_REPORT.json").read_text()) if (ART / "QUANTOS_CLOSED_LOOP_REPORT.json").exists() else {}

    # pytest count
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--co", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
        test_count = len([l for l in r.stdout.splitlines() if l.strip() and "::" in l])
    except Exception:
        test_count = 0

    modules = mapping.get("modules", {})
    done = sum(1 for m in modules.values() if m.get("status") == "done")
    partial = sum(1 for m in modules.values() if m.get("status") == "partial")

    paper_ready = bool(closed.get("gates", {}).get("paper_engine", True))
    production_ready = bool(closed.get("production_ready", False))
    major_risks = []
    if not closed.get("gates", {}).get("data_drift", True):
        major_risks.append("feature_distribution_drift")
    if not production_ready:
        major_risks.append("production_gate_not_passed")
    major_risks.append("unadjusted_price_data")
    major_risks.append("alpha158_roc_semantics_documented_not_changed")

    verdict = {
        "paper_trading_ready": paper_ready,
        "production_ready": production_ready,
        "real_broker_ready": False,
        "major_risks": major_risks,
    }

    md = _write_md(modules, done, partial, test_count, verdict, closed)
    (ART / "final_quantos_upgrade_report.md").write_text(md, encoding="utf-8")
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0


def _write_md(modules, done, partial, test_count, verdict, closed) -> str:
    lines = [
        "# QuantOS Final Upgrade Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Completion",
        "",
        f"- OS modules **done**: {done}",
        f"- OS modules **partial**: {partial}",
        f"- Tests collected: ~{test_count}",
        "",
        "## Production readiness",
        "",
        "```json",
        json.dumps(verdict, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Alpha158 policy",
        "",
        "**RETAINED** — 158-column `alpha158_compatible_v1` not downgraded. See `alpha158_audit_report.md`.",
        "",
        "## How to run",
        "",
        "```bash",
        "make audit          # architecture audit",
        "make test           # pytest",
        "make validate       # upgrade pipeline + leakage",
        "make quantos-closed-loop",
        "make prelaunch        # 上架前维护",
        "make app            # portal",
        "```",
        "",
        "## Pre-launch trading pipeline",
        "",
        "- Unified portfolio: `quant/portfolio/unified.py` → screener / paper / autopilot / live",
        "- Execution preflight: `gateway/execution/preflight.py`",
        "- Batch execute: `POST /api/v1/trading/execute-allocation`",
        "- Ticket execute: `POST /api/v1/autopilot/execute-ticket`",
        "- Portal: 「一键执行组合（实盘/无人值守）」+ Autopilot 票据执行",
        "",
        "**Live trading policy**: `disable_live_trading=true` when data drift detected; override with `allow_drift_override` + explicit unattended gates.",
        "",
        "## Gates",
        "",
    ]
    for k, v in (closed.get("gates") or {}).items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
