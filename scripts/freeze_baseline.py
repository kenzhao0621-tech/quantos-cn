#!/usr/bin/env python3
"""Freeze quantitative baseline metrics for before/after upgrade comparison."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _branch() -> str:
    try:
        return subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def main() -> int:
    from gateway.backtest.screener_backtest import run_screener_portfolio_backtest
    from quant.application.model_validation_service import ValidationConfig, get_model_validation_service
    from quant.application.screener_service import get_screener_service

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    backtest = run_screener_portfolio_backtest(preset="balanced", lookback_days=40, top_n=5)
    screen = get_screener_service().screen(preset="balanced", top_n=10, mode="eod")
    validation = None
    try:
        validation = get_model_validation_service().validate(
            ValidationConfig(preset="balanced", lookback_days=30, top_n=5)
        ).to_dict()
    except Exception as exc:
        validation = {"verdict": "ERROR", "error": str(exc)[:200]}

    manifest = {
        "frozen_at_utc": ts,
        "branch": _branch(),
        "commit": _git_head(),
        "screener": {
            "as_of_date": screen.as_of_date,
            "universe_size": screen.universe_size,
            "candidate_count": len(screen.candidates),
            "blocked": screen.blocked,
        },
        "backtest_balanced_40d": backtest,
        "model_validation": validation,
        "deployment_gates": {
            "unattended_live_disabled": True,
            "manual_confirmation_required": True,
        },
    }
    out_dir = ROOT / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "baseline_system_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(path), "backtest_status": backtest.get("status")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
