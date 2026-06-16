"""China A-share market session helpers."""

from __future__ import annotations

from datetime import datetime, time, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))


def current_session_label(now: datetime | None = None) -> str:
    """Return CLOSED | PREMARKET | MORNING | LUNCH | AFTERNOON."""
    now = now or datetime.now(CN_TZ)
    if now.weekday() >= 5:
        return "CLOSED"
    t = now.time()
    if t < time(9, 15):
        return "PREMARKET"
    if time(9, 15) <= t < time(11, 30):
        return "MORNING"
    if time(11, 30) <= t < time(13, 0):
        return "LUNCH"
    if time(13, 0) <= t < time(15, 0):
        return "AFTERNOON"
    return "CLOSED"
