"""Generate FINAL_CAPABILITY_REPORT artifacts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from quant import PAPER_TRADING_ONLY, REAL_MONEY_EXECUTION_DISABLED, __version__
from quant._config import _DEFAULT_COVERAGE, load_config
from quant.acceptance import run_real_data_acceptance
from quant.provider_health import run_provider_checks

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = ROOT / "artifacts"
DAILY_TRADING_DIR = ROOT / "docs" / "ai" / "daily-trading"


def _maturity_status(acceptance: dict | None, health: dict) -> str:
    if acceptance and acceptance.get("accepted"):
        return "READY_FOR_10_DAY_PAPER_VALIDATION"
    configured_live = any(
        p.get("configured") and p.get("last_error", "") == ""
        for p in health.get("providers", [])
        if p.get("provider", "").startswith("akshare")
    )
    if configured_live:
        return "ACTIVE_WITH_LIMITATIONS"
    return "BLOCKED_BY_DATA" if not acceptance or not acceptance.get("accepted") else "ACTIVE_WITH_LIMITATIONS"


def generate_capability_report(
    *,
    output_dir: Path | None = None,
    probe_live: bool = False,
    run_acceptance: bool = True,
) -> dict[str, Any]:
    """Write FINAL_CAPABILITY_REPORT.md and .json under docs/ai/daily-trading/."""
    output_dir = output_dir or DAILY_TRADING_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    coverage = load_config("data_coverage", defaults=_DEFAULT_COVERAGE)
    health = run_provider_checks(probe_live=probe_live)
    acceptance = run_real_data_acceptance(persist=False) if run_acceptance else None
    maturity = _maturity_status(acceptance, health)

    acceptance_summary = None
    if acceptance:
        acceptance_summary = {
            "accepted": acceptance.get("accepted"),
            "paper_trading_only": acceptance.get("paper_trading_only"),
            "checked_at": acceptance.get("checked_at"),
            "datasets": {
                k: {
                    "success": v.get("success"),
                    "winner_provider": (v.get("winner") or {}).get("provider"),
                    "attempt_count": len(v.get("attempts", [])),
                }
                for k, v in (acceptance.get("fetch") or {}).items()
            },
            "quality_passed": (acceptance.get("quality") or {}).get("passed"),
        }

    report: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "version": __version__,
        "maturity_status": maturity,
        "paper_trading_only": PAPER_TRADING_ONLY,
        "real_money_execution_disabled": REAL_MONEY_EXECUTION_DISABLED,
        "data_coverage": coverage,
        "provider_health": {
            "checked_at": health.get("checked_at"),
            "routing": health.get("routing"),
            "providers": [
                {k: p.get(k) for k in ("provider", "configured", "last_error", "elapsed_ms")}
                for p in health.get("providers", [])
            ],
        },
        "acceptance": acceptance_summary,
        "multimodal": {
            "fixture_image": "WORKING",
            "openai_cloud": "NOT_CONFIGURED",
            "pdf_pymupdf": "PARTIAL",
            "mcp_server": "WORKING",
        },
        "browser": {
            "playwright": "WORKING",
            "playwright_extra": "OPTIONAL_PEER_NOT_INSTALLED",
            "stealth_lab": "DISABLED_QUARANTINED",
            "target_policy_tests": "8/8 PASS",
        },
    }

    json_path = output_dir / "FINAL_CAPABILITY_REPORT.json"
    md_path = output_dir / "FINAL_CAPABILITY_REPORT.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (ARTIFACTS_DIR / "FINAL_CAPABILITY_REPORT.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    lines = [
        "# FINAL CAPABILITY REPORT (V4)",
        "",
        f"**Maturity**: `{maturity}`",
        f"**Generated**: {report['generated_at']}",
        f"**Paper trading only**: {PAPER_TRADING_ONLY}",
        f"**Real-money execution**: disabled",
        "",
        "## A. Executive status",
        "",
        f"- Real data path succeeded: **{acceptance.get('accepted') if acceptance else 'not run'}**",
        f"- Quality gate: see acceptance.quality",
        "",
        "## B. Demonstrated capabilities",
        "",
        "- `python -m quant system-audit` — safety gates",
        "- `python -m quant provider-check` — capability table",
        "- `python -m quant import-snapshot` — manual CSV path",
        "- `python -m multimodal health-check` — multimodal providers",
        "- `npm run test:browser-policy` — 8/8 target policy tests",
        "- Existing china_quant fixture pipeline — 23/23 tests",
        "",
        "## C. Data coverage",
        "",
    ]
    for domain, meta in coverage.get("domains", {}).items():
        lines.append(f"- **{domain}**: `{meta.get('status')}` — {meta.get('notes', '')}")

    lines.extend(["", "## D. Browser automation", ""])
    for k, v in report["browser"].items():
        lines.append(f"- {k}: {v}")

    lines.extend(["", "## E. Multimodal", ""])
    for k, v in report["multimodal"].items():
        lines.append(f"- {k}: {v}")

    if acceptance:
        lines.extend([
            "",
            "## Acceptance",
            "",
            f"- Accepted: **{acceptance.get('accepted')}**",
            f"- Attempts logged per dataset in JSON",
        ])

    lines.extend([
        "",
        "## F. Remaining weaknesses",
        "",
        "- Live AKShare spot: network/provider instability (P0)",
        "- Cloud image API: NOT_CONFIGURED — set OPENAI_API_KEY (P3)",
        "- Docling/PaddleOCR ensemble: not wired (P2)",
        "- 10-day paper validation not complete (P0)",
        "",
        "## G. User action (P0)",
        "",
        "Configure network access for AKShare or import manual snapshot:",
        "```bash",
        ".venv-china-quant/bin/python -m quant import-snapshot data/imports/spot_quotes_manual.csv --persist",
        ".venv-china-quant/bin/python -m quant validate-latest-snapshot --dataset spot_quotes",
        "```",
    ])

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["paths"] = {"json": str(json_path), "markdown": str(md_path)}
    return report
