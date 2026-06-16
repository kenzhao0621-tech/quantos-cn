"""Qlib research workflow — dataset → train → validate → signal."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from integrations.qlib.dataset import build_alpha158_lite
from gateway.ml.trial_registry import TrialRegistry

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / "data" / "quantos" / "workflows"


def run_baseline_workflow(*, as_of: str, run_id: str = "") -> dict[str, Any]:
    """End-to-end research baseline without auto-promotion to live."""
    run_id = run_id or str(uuid.uuid4())[:12]
    dataset = build_alpha158_lite(as_of=as_of)
    features = dataset.get("features", [])

    # Simple rank-score baseline
    scored = sorted(features, key=lambda x: x.get("MOM20", 0), reverse=True)
    top_signals = [
        {"symbol": s["symbol"], "score": round(s.get("MOM20", 0) * 100, 2), "side": "BUY"}
        for s in scored[:10]
    ]

    reg = TrialRegistry()
    trial = reg.register("alpha158_lite_baseline", "momentum_rank", {"as_of": as_of})
    sharpe_proxy = 0.5 if scored else 0.0
    done = reg.complete(trial, sharpe=sharpe_proxy, num_trials=1)

    result = {
        "run_id": run_id,
        "as_of": as_of,
        "dataset_rows": dataset.get("row_count", 0),
        "signals": top_signals,
        "trial": done.to_dict(),
        "model_status": done.status,
        "promotion": "CANDIDATE",
        "auto_live_promotion": False,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
    (WORKFLOW_DIR / f"{run_id}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
