"""Background intraday quote refresh — every 15 minutes during CN market hours."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Optional

from quant.freshness_contract import CST, market_session_status

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SEC = 15 * 60
_thread: Optional[threading.Thread] = None
_stop = threading.Event()
_last_tick: Optional[dict[str, Any]] = None


def intraday_refresh_status() -> dict[str, Any]:
    session, is_open = market_session_status()
    return {
        "enabled": _thread is not None and _thread.is_alive(),
        "interval_sec": REFRESH_INTERVAL_SEC,
        "market_session": session,
        "market_open": is_open,
        "last_tick": _last_tick,
    }


def _should_refresh_now() -> bool:
    _, is_open = market_session_status(datetime.now(CST))
    return is_open


def _run_refresh_cycle() -> dict[str, Any]:
    global _last_tick
    from quant.application.live_market_service import ensure_live_quotes, live_quotes_ready

    session, is_open = market_session_status(datetime.now(CST))
    if not is_open:
        tick = {"skipped": True, "reason": "market_closed", "session": session, "ts": datetime.now(CST).isoformat()}
        _last_tick = tick
        return tick

    try:
        snap = ensure_live_quotes(refresh=True, max_age_sec=REFRESH_INTERVAL_SEC)
        ready = live_quotes_ready(snap)
        tick = {
            "skipped": False,
            "session": session,
            "ts": datetime.now(CST).isoformat(),
            "row_count": snap.get("row_count") or len(snap.get("rows") or []),
            "provider": snap.get("provider"),
            "retrieved_at": snap.get("retrieved_at"),
            "quotes_ready": ready,
            "stale_fallback": bool(snap.get("stale_fallback")),
        }
        _last_tick = tick
        logger.info("intraday background refresh: %s rows ready=%s", tick.get("row_count"), ready)
        return tick
    except Exception as exc:
        tick = {"skipped": False, "error": str(exc), "session": session, "ts": datetime.now(CST).isoformat()}
        _last_tick = tick
        logger.warning("intraday background refresh failed: %s", exc)
        return tick


def _loop() -> None:
    while not _stop.is_set():
        if _should_refresh_now():
            _run_refresh_cycle()
        _stop.wait(REFRESH_INTERVAL_SEC)


def start_background_intraday_refresh() -> None:
    """Start daemon thread for 15-minute quote refresh during market hours."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="intraday-quote-refresh", daemon=True)
    _thread.start()
    logger.info("intraday background quote refresh started (interval=%ss)", REFRESH_INTERVAL_SEC)


def stop_background_intraday_refresh() -> None:
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=2.0)
