"""Daily post-close report scheduler (15:20 Asia/Shanghai on trading days)."""

from __future__ import annotations

import json
import plistlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.netlify-demo.quant.daily-report"
PLIST_DIR = ROOT / "config" / "launchd"
PLIST_PATH = PLIST_DIR / f"{LABEL}.plist"
LOG_DIR = ROOT / "docs" / "ai" / "logs"
REPORT_JSON = ROOT / "docs" / "ai" / "daily-trading" / "DAILY_REPORT_SCHEDULE.json"
WRAPPER = ROOT / "scripts" / "run-daily-report-scheduled.sh"


def _python_bin() -> Path:
    py = ROOT / ".venv-china-quant" / "bin" / "python"
    return py if py.exists() else Path("python3")


def _ensure_wrapper() -> None:
    py = _python_bin()
    WRAPPER.write_text(
        f"""#!/bin/bash
set -euo pipefail
cd "{ROOT}"
export PATH="{ROOT}/.venv-china-quant/bin:$PATH"
{py} -c "from quant.daily_report_scheduler import is_trading_day_today; import sys; sys.exit(0 if is_trading_day_today() else 0)" 
{py} - <<'PY'
from quant.daily_report_scheduler import is_trading_day_today
import sys
if not is_trading_day_today():
    print("NON_TRADING_DAY — skip daily report")
    sys.exit(0)
PY
LOCK="{ROOT}/data/gateway/daily_report.lock"
if [ -f "$LOCK" ]; then echo "duplicate run blocked"; exit 0; fi
touch "$LOCK"
trap 'rm -f "$LOCK"' EXIT
{py} "{ROOT}/scripts/run-daily-quant-pipeline.py" >> "{LOG_DIR}/daily-report.log" 2>&1
""",
        encoding="utf-8",
    )
    WRAPPER.chmod(0o755)


def is_trading_day_today() -> bool:
    from zoneinfo import ZoneInfo
    import baostock as bs
    from datetime import timedelta

    cst = ZoneInfo("Asia/Shanghai")
    today = datetime.now(cst).strftime("%Y-%m-%d")
    start = (datetime.now(cst) - timedelta(days=7)).strftime("%Y-%m-%d")
    end = (datetime.now(cst) + timedelta(days=7)).strftime("%Y-%m-%d")
    bs.login()
    rs = bs.query_trade_dates(start_date=start, end_date=end)
    days = set()
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        if row[1] == "1":
            days.add(row[0])
    bs.logout()
    return today in days


def schedule_daily_report(*, dry_run: bool = True) -> dict[str, Any]:
    _ensure_wrapper()
    PLIST_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(WRAPPER)],
        "StartCalendarInterval": {"Hour": 15, "Minute": 20},
        "StandardOutPath": str(LOG_DIR / "daily-report.stdout.log"),
        "StandardErrorPath": str(LOG_DIR / "daily-report.stderr.log"),
        "RunAtLoad": False,
    }
    PLIST_PATH.write_bytes(plistlib.dumps(plist))
    report = {
        "scheduled_at": datetime.now().isoformat(timespec="seconds"),
        "plist": str(PLIST_PATH.relative_to(ROOT)),
        "wrapper": str(WRAPPER.relative_to(ROOT)),
        "time": "15:20 Asia/Shanghai (trading-day check in wrapper)",
        "dry_run": dry_run,
        "installed": False,
    }
    if not dry_run:
        uid = subprocess.check_output(["id", "-u"], text=True).strip()
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)], capture_output=True)
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)], capture_output=True, text=True)
        report["installed"] = r.returncode == 0
        report["launchctl_stderr"] = r.stderr
    _validate_plist()
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def daily_report_schedule_status() -> dict[str, Any]:
    status = {"plist_exists": PLIST_PATH.exists(), "label": LABEL}
    if PLIST_PATH.exists():
        status["plist_path"] = str(PLIST_PATH)
    if REPORT_JSON.exists():
        status.update(json.loads(REPORT_JSON.read_text(encoding="utf-8")))
    return status


def cancel_daily_report_schedule() -> dict[str, Any]:
    uid = subprocess.check_output(["id", "-u"], text=True).strip()
    r = subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)], capture_output=True, text=True)
    return {"cancelled": r.returncode == 0, "stderr": r.stderr}


def _validate_plist() -> None:
    subprocess.run(["plutil", "-lint", str(PLIST_PATH)], capture_output=True)
