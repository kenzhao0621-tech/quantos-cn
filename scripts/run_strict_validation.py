#!/usr/bin/env python3
"""Run strict validation suite and write artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    ts = datetime.now(timezone.utc).isoformat()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    from quant.application.model_validation_service import ValidationConfig, get_model_validation_service
    from quant.validation.calibration import summarize_calibration
    from quant.validation.overfitting import deflated_sharpe_ratio, probability_backtest_overfitting, build_pbo_candidate_matrix
    from quant.validation.performance import sharpe_ratio, summarize_performance
    from quant.validation.rank_ic import summarize_rank_ic

    cfg = ValidationConfig(preset="balanced", lookback_days=120, top_n=8)
    result = get_model_validation_service().validate(cfg).to_dict()
    oos = result.get("out_of_sample", {})
    perf = oos.get("performance", {})
    rank_ic = result.get("factor_stability", {}).get("rank_ic", {})
    dsr_block = {k: oos.get(k) for k in oos if k.startswith("dsr") or k.startswith("pbo") or k.startswith("sharpe")}

    # Synthetic metric validation
    zero_sr = deflated_sharpe_ratio(0.0, n_trials=20, n_obs=252)
    pos_sr = deflated_sharpe_ratio(1.5, n_trials=3, n_obs=252)
    pbo_insuf = probability_backtest_overfitting([[0.1, 0.2]])
    cal = summarize_calibration([0.6] * 40, [1] * 20 + [0] * 20)

    strict = {
        "generated_at": ts,
        "commit": commit,
        "validation_verdict": result.get("verdict"),
        "sample_days": result.get("sample", {}).get("validation_days"),
        "oos_days": result.get("sample", {}).get("out_of_sample_days"),
        "net_oos_cumulative_return_pct": perf.get("net_cumulative_return_pct"),
        "sharpe": perf.get("sharpe"),
        "max_drawdown_pct": perf.get("max_drawdown_pct"),
        "dsr_verified": dsr_block.get("dsr_status") == "OK",
        "dsr_statistic": dsr_block.get("dsr_statistic"),
        "dsr_probability": dsr_block.get("dsr_probability"),
        "dsr_passed": dsr_block.get("dsr_passed"),
        "pbo_status": dsr_block.get("pbo_status"),
        "pbo": dsr_block.get("pbo"),
        "pbo_passed": dsr_block.get("pbo_passed"),
        "true_rank_ic_implemented": rank_ic.get("status") in ("OK", "INSUFFICIENT_SAMPLE"),
        "mean_rank_ic": rank_ic.get("mean_rank_ic"),
        "icir": rank_ic.get("icir"),
        "calibration": cal,
        "purged_kfold_passed": oos.get("purged_kfold_passed"),
        "walk_forward_passed": oos.get("walk_forward_passed"),
        "sample_status": _sample_status(result.get("sample", {}).get("validation_days", 0)),
        "synthetic_tests": {
            "dsr_zero_alpha": zero_sr.get("status"),
            "dsr_positive": pos_sr.get("dsr_probability"),
            "pbo_insufficient": pbo_insuf.get("status"),
        },
    }
    out = ROOT / "artifacts" / "strict_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(strict, indent=2, ensure_ascii=False), encoding="utf-8")

    metric_registry = {
        "generated_at": ts,
        "metrics": {
            "rank_ic": {
                "definition": "Spearman(predicted_score, realized_forward_return)",
                "formula_version": "rank_ic_v1",
                "status": rank_ic.get("status"),
            },
            "dsr": {
                "definition": "Deflated Sharpe statistic and probability under multiple testing",
                "output_types": ["dsr_statistic", "dsr_probability"],
                "formula_version": "dsr_v2",
                "status": dsr_block.get("dsr_status"),
            },
            "pbo": {
                "definition": "Probability of backtest overfitting via CSCV half-split proxy",
                "formula_version": "pbo_v2",
                "status": dsr_block.get("pbo_status"),
                "min_strategies": 8,
            },
            "top30_overlap": {
                "definition": "Recommendation stability — NOT Rank IC",
                "formula_version": "overlap_v1",
                "status": "OK",
            },
        },
    }
    (ROOT / "artifacts" / "metric_registry.json").write_text(
        json.dumps(metric_registry, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "strict_validation": str(out), "verdict": result.get("verdict")}, ensure_ascii=False))
    return 0


def _sample_status(n_days: int) -> str:
    if n_days < 30:
        return "INSUFFICIENT"
    if n_days < 80:
        return "PRELIMINARY"
    if n_days < 120:
        return "MODERATE"
    return "MATURE"


if __name__ == "__main__":
    raise SystemExit(main())
