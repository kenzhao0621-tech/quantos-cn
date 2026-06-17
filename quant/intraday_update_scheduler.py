"""Local intraday data refresh scheduler for QuantOS CN.

Creates a macOS launchd plist with five weekday refresh windows:
pre-open, morning session, lunch, afternoon session, and close. The generated
wrapper refreshes live/near-live spot data into data/gateway/live_snapshot.json.

No public deployment or real trading is enabled by this scheduler.
"""

from __future__ import annotations

import json
import plistlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.netlify-demo.quant.intraday-refresh"
PLIST_DIR = ROOT / "config" / "launchd"
PLIST_PATH = PLIST_DIR / f"{LABEL}.plist"
WRAPPER = ROOT / "scripts" / "run-intraday-refresh-scheduled.sh"
REPORT_JSON = ROOT / "docs" / "ai" / "daily-trading" / "INTRADAY_REFRESH_SCHEDULE.json"
LIVE_STATE = ROOT / "data" / "gateway" / "live_snapshot.json"
LOG_DIR = ROOT / "docs" / "ai" / "logs"

SLOTS = [
    {"slot": "pre_open", "label": "开盘前", "hour": 9, "minute": 15},
    {"slot": "morning", "label": "上午盘中", "hour": 10, "minute": 30},
    {"slot": "lunch", "label": "中午收盘", "hour": 11, "minute": 35},
    {"slot": "afternoon", "label": "下午盘中", "hour": 14, "minute": 0},
    {"slot": "close", "label": "工作日收盘", "hour": 15, "minute": 5},
]


def _python_bin() -> Path:
    py = ROOT / ".venv-china-quant" / "bin" / "python"
    return py if py.exists() else Path("python3")


def run_intraday_refresh(slot: str = "manual") -> dict[str, Any]:
    from quant.market_data_fabric import MarketDataFabric

    fetched = MarketDataFabric().fetch("spot_quotes", live_only=True, require_live=False, min_rows=1000)
    record: dict[str, Any]
    if fetched.ok and fetched.result:
        payload = fetched.result.payload or {}
        rows = payload.get("rows", [])
        record = {
            "success": True,
            "slot": slot,
            "provider": fetched.result.provider,
            "row_count": len(rows),
            "retrieved_at": fetched.result.retrieved_at,
            "source_event_time": payload.get("source_event_time"),
            "freshness": payload.get("freshness") or fetched.result.freshness,
            "market_date": payload.get("market_date"),
            "is_live": bool(payload.get("is_live") or fetched.result.is_live),
        }
    else:
        record = {
            "success": False,
            "slot": slot,
            "retrieved_at": datetime.now().isoformat(timespec="seconds"),
            "reason": fetched.selection_reason,
            "attempts": [a.to_dict() for a in fetched.attempts],
        }
    LIVE_STATE.parent.mkdir(parents=True, exist_ok=True)
    LIVE_STATE.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def _ensure_wrapper() -> None:
    py = _python_bin()
    WRAPPER.write_text(
        f"""#!/bin/bash
set -euo pipefail
cd "{ROOT}"
export PATH="{ROOT}/.venv-china-quant/bin:$PATH"
SLOT="${{1:-scheduled}}"
"{py}" - <<'PY' "$SLOT" >> "{LOG_DIR}/intraday-refresh.log" 2>&1
import sys
from quant.intraday_update_scheduler import run_intraday_refresh
print(run_intraday_refresh(sys.argv[1]))
PY
""",
        encoding="utf-8",
    )
    WRAPPER.chmod(0o755)


def schedule_intraday_refresh(*, dry_run: bool = True) -> dict[str, Any]:
    _ensure_wrapper()
    PLIST_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    intervals = [
        {"Weekday": [1, 2, 3, 4, 5], "Hour": s["hour"], "Minute": s["minute"]}
        for s in SLOTS
    ]
    plist = {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(WRAPPER), "scheduled"],
        "StartCalendarInterval": intervals,
        "StandardOutPath": str(LOG_DIR / "intraday-refresh.stdout.log"),
        "StandardErrorPath": str(LOG_DIR / "intraday-refresh.stderr.log"),
        "RunAtLoad": False,
    }
    PLIST_PATH.write_bytes(plistlib.dumps(plist))
    report = {
        "scheduled_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "installed": False,
        "label": LABEL,
        "plist": str(PLIST_PATH.relative_to(ROOT)),
        "wrapper": str(WRAPPER.relative_to(ROOT)),
        "slots": SLOTS,
    }
    if not dry_run:
        uid = subprocess.check_output(["id", "-u"], text=True).strip()
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)], capture_output=True)
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)], capture_output=True, text=True)
        report["installed"] = r.returncode == 0
        report["launchctl_stderr"] = r.stderr
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def intraday_schedule_status() -> dict[str, Any]:
    status = {"label": LABEL, "plist_exists": PLIST_PATH.exists(), "slots": SLOTS}
    if REPORT_JSON.exists():
        status.update(json.loads(REPORT_JSON.read_text(encoding="utf-8")))
    return status
