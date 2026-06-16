"""One-shot launchd scheduling for next open-session live test (macOS)."""

from __future__ import annotations

import json
import plistlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.netlify-demo.quant.live-market-hours-test"
PLIST_DIR = ROOT / "config" / "launchd"
PLIST_PATH = PLIST_DIR / f"{LABEL}.plist"
LOG_DIR = ROOT / "docs" / "ai" / "logs"
REPORT_JSON = ROOT / "docs" / "ai" / "daily-trading" / "LIVE_MARKET_HOURS_TEST.json"
REPORT_MD = ROOT / "docs" / "ai" / "daily-trading" / "LIVE_MARKET_HOURS_TEST.md"


def _next_open_session_at_0940() -> datetime:
    from quant.backfill import _trade_dates_baostock
    from zoneinfo import ZoneInfo

    cst = ZoneInfo("Asia/Shanghai")
    now = datetime.now(cst)
    dates = _trade_dates_baostock(30)
    for d in dates:
        y, m, day = int(d[:4]), int(d[4:6]), int(d[6:8])
        target = datetime(y, m, day, 9, 40, 0, tzinfo=cst)
        if target > now:
            return target
    return now


def schedule_live_test(*, dry_run: bool = True) -> dict[str, Any]:
    target = _next_open_session_at_0940()
    PLIST_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    py = ROOT / ".venv-china-quant" / "bin" / "python"
    if not py.exists():
        py = Path("python3")

    script = ROOT / "scripts" / "run-live-market-hours-test.sh"
    script.write_text(
        f"""#!/bin/bash
set -euo pipefail
cd "{ROOT}"
export PATH="{ROOT}/.venv-china-quant/bin:$PATH"
{py} -m quant freshness-watchdog > "{LOG_DIR}/live-test-watchdog.log" 2>&1
RUN_ID=$({py} -c "from quant.run_context import new_run_id; print(new_run_id())")
{py} -m quant fabric-fetch --datasets spot_quotes --persist --live-only --require-live >> "{LOG_DIR}/live-test-fetch.log" 2>&1 || true
{py} -m quant cross-source-reconcile --dataset spot_quotes --run-id "$RUN_ID" >> "{LOG_DIR}/live-test-reconcile.log" 2>&1 || true
launchctl bootout gui/$(id -u) "{PLIST_PATH}" 2>/dev/null || true
""",
        encoding="utf-8",
    )
    script.chmod(0o755)

    plist = {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(script)],
        "StartCalendarInterval": {
            "Month": target.month,
            "Day": target.day,
            "Hour": 9,
            "Minute": 40,
        },
        "StandardOutPath": str(LOG_DIR / "live-test.stdout.log"),
        "StandardErrorPath": str(LOG_DIR / "live-test.stderr.log"),
        "RunAtLoad": False,
    }
    PLIST_PATH.write_bytes(plistlib.dumps(plist))

    report = {
        "scheduled_at": datetime.now().isoformat(timespec="seconds"),
        "target_session": target.isoformat(),
        "plist": str(PLIST_PATH.relative_to(ROOT)),
        "script": str(script.relative_to(ROOT)),
        "dry_run": dry_run,
        "installed": False,
        "note": "One-shot job removes itself after run via bootout in script",
    }

    if not dry_run:
        uid = subprocess.check_output(["id", "-u"], text=True).strip()
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)], capture_output=True)
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)], capture_output=True, text=True)
        report["installed"] = r.returncode == 0
        report["launchctl_stderr"] = r.stderr

    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    REPORT_MD.write_text(
        "\n".join([
            "# LIVE_MARKET_HOURS_TEST",
            "",
            f"Target: {target.isoformat()}",
            f"Dry run: {dry_run}",
            f"Installed: {report['installed']}",
            "",
            "Tests: session=open, row_count>=5000, quote age SLA, cross-source",
        ]),
        encoding="utf-8",
    )
    return report
