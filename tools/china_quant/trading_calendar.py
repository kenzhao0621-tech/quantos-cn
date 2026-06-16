"""Trading calendar — fixture + optional AKShare."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def load_calendar_fixture(fixtures_dir: Path) -> set[str]:
    path = fixtures_dir / "trading_calendar.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("trading_days", []))


def is_trading_day(d: str, *, fixtures_dir: Optional[Path] = None, use_akshare: bool = False) -> bool:
    if fixtures_dir:
        cal = load_calendar_fixture(fixtures_dir)
        if cal:
            return d in cal
    if use_akshare:
        from tools.china_quant.data import is_trading_day_akshare

        return is_trading_day_akshare(d)
    dt = datetime.strptime(d, "%Y-%m-%d").date()
    return dt.weekday() < 5


def next_trading_day_hint(d: str, fixtures_dir: Path) -> str:
    cal = sorted(load_calendar_fixture(fixtures_dir))
    for day in cal:
        if day > d:
            return day
    return "unknown"
