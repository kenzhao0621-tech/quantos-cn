"""Alpha158 audit — document existing implementation; do not modify formulas."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts"


def run_alpha158_audit() -> dict:
    from quant.features.alpha158 import FEATURE_VERSION, WINDOWS, ROLL_OPS, KBAR_NAMES, feature_column_names

    cols = feature_column_names()
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "feature_version": FEATURE_VERSION,
        "n_features": len(cols),
        "inputs": ["open", "high", "low", "close", "vol", "amount"],
        "windows": list(WINDOWS),
        "kbar_features": list(KBAR_NAMES),
        "rolling_ops": list(ROLL_OPS),
        "feature_columns": cols,
        "winsorize": "cross_section per trade_date at cache build (alpha158.py winsorize_frame)",
        "neutralization_in_ml_path": "via parquet cache; screener uses separate z-map layers",
        "lookahead_controls": [
            "trade_date <= as_of in ml_scorer",
            "sorted ascending per symbol before rolling",
            "EOD close semantics",
        ],
        "missing_value_handling": "NaN from rolling warmup; filled 0 at ML predict",
        "duplicate_factor_risk": "High correlation expected within ROC/MA/RET families — see factor_correlation_report.json",
        "policy": "RETAIN_EXISTING — no formula changes in this upgrade",
    }
    md = _md_report(report)
    (ART / "alpha158_audit_report.md").write_text(md, encoding="utf-8")

    conflicts = {
        "generated_at": report["generated_at"],
        "policy": "default_retain_existing_alpha158",
        "conflicts": [
            {
                "factor_family": "ROC{w}",
                "existing": "c.shift(w) / c - 1.0",
                "textbook": "c / c.shift(w) - 1.0",
                "decision": "RETAIN",
                "reason": "Retraining LGBM would invalidate model; document as alpha158_compatible_v1 semantics",
            },
            {
                "factor_family": "BETA{w}",
                "existing": "ret.rolling(w).cov(c.pct_change()) / var(c.pct_change())",
                "textbook": "cov(ret, market_ret) / var(market_ret)",
                "decision": "RETAIN",
                "reason": "Self-beta proxy; not market beta — documented difference",
            },
            {
                "name": "alpha158_lite vs alpha158_compatible_v1",
                "existing_screener": "price_momentum_lite in alpha_blend.py (4 factors)",
                "existing_ml": "158 columns in alpha158.py",
                "decision": "RETAIN_BOTH",
                "reason": "Different layers; do not merge or downgrade",
            },
        ],
    }
    (ART / "factor_conflict_report.md").write_text(_conflict_md(conflicts), encoding="utf-8")
    return report


def _md_report(r: dict) -> str:
    lines = [
        "# Alpha158 Audit Report",
        "",
        f"Version: `{r['feature_version']}` | Features: **{r['n_features']}**",
        "",
        "## Inputs",
        ", ".join(f"`{x}`" for x in r["inputs"]),
        "",
        "## Policy",
        r["policy"],
        "",
        "## Lookahead controls",
    ]
    lines.extend(f"- {x}" for x in r["lookahead_controls"])
    lines.extend([
        "",
        "## Feature columns (158)",
        "",
        ", ".join(f"`{c}`" for c in r["feature_columns"][:40]) + " …",
        "",
        "Full list in `feature_columns` field of this audit JSON artifact.",
    ])
    return "\n".join(lines)


def _conflict_md(c: dict) -> str:
    lines = ["# Factor Conflict Report", "", f"Policy: **{c['policy']}**", ""]
    for item in c["conflicts"]:
        lines.append(f"### {item.get('factor_family') or item.get('name')}")
        for k, v in item.items():
            if k not in ("factor_family", "name"):
                lines.append(f"- **{k}**: {v}")
        lines.append("")
    return "\n".join(lines)
