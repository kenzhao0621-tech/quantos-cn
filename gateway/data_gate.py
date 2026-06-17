"""Fast data-quality gate for trading paths — warehouse + snapshot, no blocking network."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from gateway.config import ROOT

WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"
LIVE_SNAPSHOT = ROOT / "data" / "gateway" / "live_snapshot.json"
CACHE_PATH = ROOT / "data" / "gateway" / "data_gate_cache.json"
CACHE_TTL_SEC = 120


def _parse_trade_date(s: str) -> datetime | None:
    raw = str(s).replace("-", "")[:8]
    try:
        return datetime.strptime(raw, "%Y%m%d")
    except ValueError:
        return None


def _warehouse_status() -> dict[str, Any]:
    if not WAREHOUSE.exists():
        return {"ok": False, "reason": "warehouse missing", "trade_dates": 0}
    try:
        import duckdb

        con = duckdb.connect(str(WAREHOUSE), read_only=True)
        row = con.execute(
            "SELECT COUNT(DISTINCT trade_date), MAX(trade_date), COUNT(DISTINCT ts_code) FROM daily_bars"
        ).fetchone()
        con.close()
        dates, latest, symbols = int(row[0] or 0), str(row[1] or ""), int(row[2] or 0)
        latest_dt = _parse_trade_date(latest)
        stale_days = (datetime.now() - latest_dt).days if latest_dt else 999
        return {
            "ok": dates >= 60,
            "trade_dates": dates,
            "latest_trade_date": latest,
            "symbol_count": symbols,
            "stale_calendar_days": stale_days,
            "reason": None if dates >= 60 else "insufficient history",
        }
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:120], "trade_dates": 0}


def _live_snapshot_status() -> dict[str, Any]:
    if not LIVE_SNAPSHOT.exists():
        return {"ok": False, "reason": "no live snapshot", "age_sec": None}
    try:
        data = json.loads(LIVE_SNAPSHOT.read_text(encoding="utf-8"))
        retrieved = data.get("retrieved_at") or data.get("checked_at")
        age_sec = None
        if retrieved:
            try:
                ts = datetime.fromisoformat(str(retrieved).replace("Z", "+00:00"))
                age_sec = int((datetime.now(ts.tzinfo) - ts).total_seconds())
            except Exception:
                pass
        mtime_age = int(datetime.now().timestamp() - LIVE_SNAPSHOT.stat().st_mtime)
        age = age_sec if age_sec is not None else mtime_age
        return {
            "ok": age < 3600,
            "age_sec": age,
            "row_count": data.get("row_count") or len(data.get("rows") or []),
            "provider": data.get("provider"),
            "retrieved_at": retrieved,
        }
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:80], "age_sec": None}


def evaluate_data_gate(*, probe_live: bool = False, force_refresh: bool = False) -> dict[str, Any]:
    if not force_refresh and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            checked = datetime.fromisoformat(cached["checked_at"])
            if (datetime.now() - checked).total_seconds() < CACHE_TTL_SEC:
                return cached
        except Exception:
            pass

    from quant.freshness_contract import market_session_status

    now = datetime.now()
    session, is_open = market_session_status(now)
    wh = _warehouse_status()
    live = _live_snapshot_status()

    blockers: list[str] = []
    if not wh.get("ok"):
        blockers.append(f"WAREHOUSE: {wh.get('reason', 'bad')}")
    if wh.get("stale_calendar_days", 0) > 5:
        blockers.append(f"EOD_STALE_{wh.get('stale_calendar_days')}d")
    if is_open and not live.get("ok"):
        blockers.append("LIVE_SNAPSHOT_STALE")

    if blockers:
        verdict = "BLOCKED_BY_DATA"
    elif is_open:
        verdict = "INTRADAY_OK" if live.get("ok") else "EOD_ONLY"
    else:
        verdict = "EOD_OK"

    if probe_live and is_open:
        try:
            from quant.freshness_watchdog import run_freshness_watchdog

            wd = run_freshness_watchdog(probe_live=True)
            if wd.get("verdict") == "BLOCKED_BY_DATA":
                blockers.append("LIVE_PROBE_FAILED")
                verdict = "BLOCKED_BY_DATA"
        except Exception as exc:
            blockers.append(f"LIVE_PROBE_ERROR:{str(exc)[:60]}")

    report = {
        "checked_at": now.isoformat(timespec="seconds"),
        "market_session": session,
        "is_open": is_open,
        "verdict": verdict,
        "blockers": blockers,
        "warehouse": wh,
        "live_snapshot": live,
        "trade_allowed_modes": {
            "screener_eod": wh.get("ok", False),
            "screener_live_cached": wh.get("ok", False) and live.get("ok", False),
            "order_ticket": wh.get("ok", False) and verdict != "BLOCKED_BY_DATA",
            "paper_shadow": wh.get("ok", False),
        },
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
