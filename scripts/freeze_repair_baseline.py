#!/usr/bin/env python3
"""Freeze repair baseline before quant reliability upgrade."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "artifacts" / "repair_baseline"


def _git(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(["git"] + cmd, cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    from gateway.backtest.screener_backtest import run_screener_portfolio_backtest
    from quant.application.model_validation_service import ValidationConfig, get_model_validation_service
    from quant.application.screener_service import get_screener_service

    backtest = run_screener_portfolio_backtest(preset="balanced", lookback_days=40, top_n=5)
    screen = get_screener_service().screen(preset="balanced", top_n=10, mode="eod")
    try:
        validation = get_model_validation_service().validate(
            ValidationConfig(preset="balanced", lookback_days=40, top_n=5)
        ).to_dict()
    except Exception as exc:
        validation = {"verdict": "ERROR", "error": str(exc)[:300]}

    e2e_failures = {"case": "overview-body", "status": "FAIL", "note": "selector missing before repair"}
    if (ROOT / "docs" / "ai" / "app" / "04_API_FUNCTIONAL_ACCEPTANCE.json").exists():
        e2e_failures = json.loads((ROOT / "docs" / "ai" / "app" / "04_API_FUNCTIONAL_ACCEPTANCE.json").read_text())

    artifacts = {
        "frozen_at": ts,
        "starting_branch": _git(["branch", "--show-current"]),
        "starting_commit": _git(["rev-parse", "HEAD"]),
        "python": sys.version.split()[0],
    }
    (OUT / "build_manifest.json").write_text(json.dumps(artifacts, indent=2), encoding="utf-8")
    (OUT / "metrics.json").write_text(json.dumps(backtest, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "validation.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "screener_sample.json").write_text(
        json.dumps({
            "as_of_date": screen.as_of_date,
            "candidates": [c.__dict__ if hasattr(c, "__dict__") else str(c) for c in screen.candidates[:5]],
            "blocked": screen.blocked,
        }, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (OUT / "e2e_failures.json").write_text(json.dumps(e2e_failures, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "api_schema.json").write_text(json.dumps({
        "endpoints": ["/health", "/ready", "/build-info", "/api/v1/system/status", "/api/v1/deployment/eligibility"],
    }, indent=2), encoding="utf-8")

    print(json.dumps({"ok": True, "out_dir": str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
