"""Unified market data status for portal — EOD dates, live snapshot, human labels."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from gateway.config import ROOT

WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"
LIVE_SNAPSHOT = ROOT / "data" / "gateway" / "live_snapshot.json"


def _fmt_date(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).replace("-", "")[:8]
    if len(s) == 8 and s.isdigit():
        return f"{s[4:6]}/{s[6:8]}"
    return str(raw)[:10]


def _warehouse_dates() -> dict[str, Any]:
    if not WAREHOUSE.exists():
        return {"ok": False, "daily_latest": None, "index_latest": None}
    try:
        import duckdb

        con = duckdb.connect(str(WAREHOUSE), read_only=True)
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        daily = None
        index = None
        if "daily_bars" in tables:
            daily = con.execute("SELECT max(trade_date) FROM daily_bars").fetchone()[0]
        if "index_bars" in tables:
            index = con.execute("SELECT max(trade_date) FROM index_bars").fetchone()[0]
        con.close()
        daily_s = str(daily).replace("-", "")[:8] if daily else None
        index_s = str(index).replace("-", "")[:8] if index else None
        display = daily_s or index_s
        if daily_s and index_s and daily_s != index_s:
            lag = "index_lags" if index_s < daily_s else "ok"
        else:
            lag = "ok"
        return {
            "ok": bool(display),
            "daily_latest": daily_s,
            "index_latest": index_s,
            "display_latest": display,
            "index_lags_daily": lag == "index_lags",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


def _live_status() -> dict[str, Any]:
    if not LIVE_SNAPSHOT.exists():
        return {"ok": False, "reason": "尚未刷新实时行情", "row_count": 0}
    try:
        data = json.loads(LIVE_SNAPSHOT.read_text(encoding="utf-8"))
        if data.get("blocked") or data.get("success") is False:
            return {
                "ok": False,
                "reason": data.get("reason") or "实时源不可用",
                "row_count": 0,
                "attempts": len(data.get("attempts") or []),
            }
        retrieved = data.get("retrieved_at")
        age_sec = None
        if retrieved:
            try:
                ts = datetime.fromisoformat(str(retrieved).replace("Z", "+00:00"))
                age_sec = int((datetime.now(ts.tzinfo) - ts).total_seconds())
            except Exception:
                pass
        if age_sec is None:
            age_sec = int(datetime.now().timestamp() - LIVE_SNAPSHOT.stat().st_mtime)
        rows = data.get("rows") or []
        row_count = data.get("row_count") or len(rows)
        # Honesty gate: a cached fallback or an old snapshot must never be presented
        # as live-OK (refactor audit DATA_SOURCE_AUDIT §6).
        stale_fallback = bool(data.get("stale_fallback"))
        too_old = age_sec is not None and age_sec > 3600
        stale = stale_fallback or too_old
        result: dict[str, Any] = {
            "ok": row_count > 100 and not stale,
            "retrieved_at": retrieved,
            "age_sec": age_sec,
            "row_count": row_count,
            "provider": data.get("provider"),
            "market_date": data.get("market_date"),
            "freshness": data.get("freshness"),
            "stale": stale,
        }
        if stale:
            result["reason"] = "缓存回落（非实时）" if stale_fallback else "快照已超过1小时"
        return result
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:80], "row_count": 0}


def get_market_status_summary() -> dict[str, Any]:
    wh = _warehouse_dates()
    live = _live_status()
    from gateway.env_loader import tushare_configured

    tushare_ok = tushare_configured()

    daily_label = _fmt_date(wh.get("daily_latest")) or "无"
    index_label = _fmt_date(wh.get("index_latest")) or "无"
    if live.get("ok"):
        live_ts = str(live.get("retrieved_at") or "")[:19].replace("T", " ")
        live_label = live_ts or "刚刚"
    elif live.get("stale"):
        stale_ts = str(live.get("retrieved_at") or "")[:19].replace("T", " ")
        live_label = f"{live.get('reason') or '已过期'}，最后更新 {stale_ts}" if stale_ts else (live.get("reason") or "已过期")
    else:
        live_label = live.get("reason") or "未连接"

    pill = f"日线 {daily_label}"
    if wh.get("index_lags_daily"):
        pill += f" · 指数 {index_label}(待同步)"
    if live.get("ok"):
        pill += " · 实时 OK"
    elif live.get("stale"):
        pill += " · 实时已过期"
    else:
        pill += " · 实时待同步"

    return {
        "warehouse": wh,
        "live": live,
        "tushare_configured": tushare_ok,
        "labels": {
            "eod": f"个股日线截至 {daily_label}",
            "index": f"指数截至 {index_label}" + (" — 请点击「同步全部数据」更新指数" if wh.get("index_lags_daily") else ""),
            "live": f"实时行情：{live_label}" if live.get("ok") else f"实时行情：{live_label}（请点「同步全部数据」）",
            "pill": pill,
        },
        "needs_index_sync": wh.get("index_lags_daily", False),
        "needs_live_refresh": not live.get("ok"),
    }
