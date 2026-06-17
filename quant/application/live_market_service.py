"""Application-layer live market service.

The portal BFF calls this service; provider/fabric details stay out of API
routes so the frontend boundary remains stable.
"""

from __future__ import annotations

import time as _time
from datetime import datetime, time
_SNAPSHOT_CACHE: tuple[float, dict[str, Any]] | None = None

from typing import Any
from zoneinfo import ZoneInfo


def intraday_slots() -> list[dict[str, Any]]:
    cst = ZoneInfo("Asia/Shanghai")
    now = datetime.now(cst)
    slots = [
        ("pre_open", "开盘前", time(9, 15), "集合竞价前：刷新昨夜/盘前数据，生成今日观察池"),
        ("morning", "上午盘中", time(10, 30), "确认开盘后量价是否支持候选"),
        ("lunch", "中午收盘", time(11, 35), "午间复盘：筛掉高开回落/流动性衰减"),
        ("afternoon", "下午盘中", time(14, 0), "尾盘前确认是否继续持有模拟计划"),
        ("close", "工作日收盘", time(15, 5), "收盘后落盘，准备 T+1 验证和日报"),
    ]
    return [
        {
            "slot": key,
            "label": label,
            "time": f"{t.hour:02d}:{t.minute:02d}",
            "due_today": (now.time() >= t and now.weekday() < 5),
            "purpose": purpose,
        }
        for key, label, t, purpose in slots
    ]


def fetch_live_snapshot(*, require_live: bool) -> dict[str, Any]:
    global _SNAPSHOT_CACHE
    now = _time.time()
    if _SNAPSHOT_CACHE and now - _SNAPSHOT_CACHE[0] < 20:
        snap = dict(_SNAPSHOT_CACHE[1])
        snap["cache_hit"] = True
        return snap

    from quant.market_data_fabric import MarketDataFabric

    fetched = MarketDataFabric().fetch(
        "spot_quotes",
        live_only=True,
        require_live=require_live,
        min_rows=1000,
    )
    attempts = [a.to_dict() for a in fetched.attempts]
    if not fetched.ok or not fetched.result:
        return {
            "success": False,
            "blocked": True,
            "reason": fetched.selection_reason,
            "attempts": attempts,
            "slots": intraday_slots(),
        }
    payload = fetched.result.payload or {}
    rows = list(payload.get("rows", []))
    adv = sum(1 for r in rows if float(r.get("change_pct") or 0) > 0)
    dec = sum(1 for r in rows if float(r.get("change_pct") or 0) < 0)
    top_up = sorted(rows, key=lambda r: float(r.get("change_pct") or 0), reverse=True)[:10]
    top_down = sorted(rows, key=lambda r: float(r.get("change_pct") or 0))[:10]
    snap = {
        "success": True,
        "blocked": False,
        "provider": fetched.result.provider,
        "row_count": len(rows),
        "retrieved_at": fetched.result.retrieved_at,
        "source_event_time": payload.get("source_event_time"),
        "market_date": payload.get("market_date"),
        "freshness": payload.get("freshness") or fetched.result.freshness,
        "is_live": bool(payload.get("is_live") or fetched.result.is_live),
        "breadth": {"advancers": adv, "decliners": dec, "flat": max(0, len(rows) - adv - dec)},
        "top_up": [
            {"code": r.get("code"), "name": r.get("name"), "price": r.get("price"), "change_pct": r.get("change_pct"), "amount": r.get("amount")}
            for r in top_up
        ],
        "top_down": [
            {"code": r.get("code"), "name": r.get("name"), "price": r.get("price"), "change_pct": r.get("change_pct"), "amount": r.get("amount")}
            for r in top_down
        ],
        "slots": intraday_slots(),
        "attempts": attempts,
    }
    _SNAPSHOT_CACHE = (now, snap)
    return snap
