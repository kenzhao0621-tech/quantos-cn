"""Factor registry artifacts — sync configs → artifacts without changing runtime scoring."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts"
CONFIG = ROOT / "configs" / "factor_registry.yaml"


def write_factor_artifacts() -> dict:
    ART.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists():
        shutil.copy(CONFIG, ART / "factor_registry.yaml")

    base_factors = ["ret_20", "ret_60", "trend", "vol_20", "avg_amount", "pe", "pb", "dividend_yield", "market_cap", "disclosure_flag"]
    alpha158 = {
        "name": "alpha158_compatible_v1",
        "n_features": 158,
        "path": "quant/features/alpha158.py",
        "cache": "data/parquet/features/alpha158/alpha158_wide.parquet",
        "validation_status": "CANDIDATE",
        "enabled": True,
        "policy": "RETAIN — do not replace with lite spec list",
    }
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_factors": {f: {"enabled": True, "validation_status": "APPROVED"} for f in base_factors},
        "alpha158": alpha158,
        "screener_blend": {
            "name": "price_momentum_lite",
            "path": "quant/screener/alpha_blend.py",
            "validation_status": "APPROVED",
            "note": "Separate from full Alpha158 ML features",
        },
        "simulation_features_enabled": 0,
        "rank_ic_gate": {"min_mean": 0.02, "min_icir": 0.20},
    }
    mm = ROOT / "artifacts" / "model_metrics.json"
    if mm.exists():
        ric = json.loads(mm.read_text()).get("rank_ic_oos") or {}
        report["alpha158_lgbm"] = {
            "mean_rank_ic": ric.get("mean_rank_ic"),
            "icir": ric.get("icir"),
            "passed_rank_ic_gate": float(ric.get("mean_rank_ic") or 0) >= 0.02,
            "validation_status": "CANDIDATE",
        }
    (ART / "factor_validation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
