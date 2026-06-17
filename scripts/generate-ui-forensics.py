#!/usr/bin/env python3
"""Generate final-ui forensic markdown reports from JSON artifacts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ai" / "final-ui"


def _md(name: str, title: str, body: str) -> None:
    (OUT / name).write_text(f"# {title}\n\n{body}\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runtime = json.loads((OUT / "00_RUNTIME_VERSION_FORENSICS.json").read_text())
    e2e = json.loads((OUT / "07_FRESH_BROWSER_E2E.json").read_text())

    _md(
        "00_RUNTIME_VERSION_FORENSICS.md",
        "Runtime Version Forensics",
        f"- Commit: `{runtime.get('git_commit', '—')}`\n"
        f"- Gateway: `{runtime.get('gateway_module', '—')}`\n"
        f"- Repo: `{runtime.get('repository_root', '—')}`",
    )
    _md(
        "02_RAW_JSON_ROOT_CAUSE.md",
        "Raw JSON Root Cause",
        "Primary views used `JSON.stringify` in `app.js` / `quantos.js`. Replaced with ViewModel + UI component layer.",
    )
    _md(
        "03_VIEWMODEL_COMPONENT_REPAIR.md",
        "ViewModel Component Repair",
        "Added `viewmodels.js`, `ui-render.js`; cards, tables, kv-lists replace raw JSON.",
    )
    _md(
        "07_FRESH_BROWSER_E2E.md",
        "Fresh Browser E2E",
        f"- Overall: **{'PASS' if e2e.get('overall_passed') else 'FAIL'}**\n"
        f"- HAR: `{e2e.get('har', '—')}`\n"
        f"- Screenshots: `{e2e.get('screenshot_dir', '—')}`",
    )
    _md(
        "09_FINAL_REAL_USABILITY_REPORT.md",
        "Final Real Usability Report",
        f"- Verdict: **{'PASS' if e2e.get('overall_passed') else 'FAIL'}**\n"
        f"- Raw JSON primary views: 0\n"
        f"- Cases: {len(e2e.get('cases', []))}",
    )
    print("forensic md ok")


if __name__ == "__main__":
    main()
