"""Application-layer live market service.

The portal BFF calls this service; provider/fabric details stay out of API
routes so the frontend boundary remains stable.
"""

from __future__ import annotations

import json
import time as _time
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_SNAPSHOT_CACHE: tuple[float, dict[str, Any]] | None = None
ROOT = Path(__file__).resolve().parents[2]
LIVE_STATE_PATH = ROOT / "data" / "gateway" / "live_snapshot.json"


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


def snapshot_rows(snap: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return quote rows from snapshot — top-level or nested in provider attempts."""
    if not snap:
        return []
    rows = snap.get("rows") or []
    if rows:
        return list(rows)
    for att in snap.get("attempts") or []:
        if str(att.get("status", "")).upper() != "SUCCESS":
            continue
        payload = att.get("payload") or {}
        nested = payload.get("rows") or []
        if nested:
            return list(nested)
    return []


def normalize_ts_code(raw: str) -> str:
    """Normalize exchange code to ts_code (600519.SH)."""
    s = str(raw or "").strip().upper()
    if "." in s and len(s.split(".", 1)[0]) >= 6:
        return s
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return s
    code = digits[-6:].zfill(6)
    if s.lower().startswith("sh") or code.startswith("6"):
        return f"{code}.SH"
    if s.lower().startswith("bj") or code.startswith(("4", "8", "9")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def normalize_snapshot_for_persist(snap: dict[str, Any]) -> dict[str, Any]:
    """Ensure top-level rows exist; slim heavy nested attempt payloads."""
    out = dict(snap)
    rows = snapshot_rows(out)
    out["rows"] = rows
    out["row_count"] = len(rows) or int(out.get("row_count") or 0)
    slim_attempts: list[dict[str, Any]] = []
    for att in out.get("attempts") or []:
        a = dict(att)
        payload = a.get("payload")
        if isinstance(payload, dict) and payload.get("rows"):
            p = dict(payload)
            p["row_count"] = len(payload["rows"])
            p.pop("rows", None)
            a["payload"] = p
        slim_attempts.append(a)
    if slim_attempts:
        out["attempts"] = slim_attempts
    return out


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
        from gateway.brokers.waf_recovery import humanize_provider_error

        reason = humanize_provider_error(fetched.selection_reason or "provider blocked")
        return {
            "success": False,
            "blocked": True,
            "reason": reason,
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
        "rows": rows,
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


def persist_live_snapshot(snap: dict[str, Any]) -> Path:
    """Write snapshot (including full rows) for screener + paper mark-to-market."""
    LIVE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_snapshot_for_persist(snap)
    LIVE_STATE_PATH.write_text(json.dumps(normalized, ensure_ascii=False), encoding="utf-8")
    return LIVE_STATE_PATH


def _load_persisted_snapshot() -> dict[str, Any] | None:
    if not LIVE_STATE_PATH.exists():
        return None
    try:
        return json.loads(LIVE_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def live_quotes_ready(snap: dict[str, Any] | None, *, min_rows: int = 100) -> bool:
    """True when snapshot has enough real quote rows and is not provider-blocked."""
    if not snap or snap.get("blocked"):
        return False
    return len(snapshot_rows(snap)) >= min_rows


def ensure_live_quotes(*, refresh: bool = False, max_age_sec: int = 120) -> dict[str, Any]:
    """Load cached live quotes or fetch+persist when stale/missing."""
    global _SNAPSHOT_CACHE
    now = _time.time()

    def _age_ok(cached: dict[str, Any]) -> bool:
        retrieved = cached.get("retrieved_at") or ""
        if not retrieved:
            return False
        try:
            ts = datetime.fromisoformat(str(retrieved).replace("Z", "+00:00")).timestamp()
            return (now - ts) <= max_age_sec
        except Exception:
            return False

    if not refresh and LIVE_STATE_PATH.exists():
        cached = _load_persisted_snapshot()
        if cached:
            rows = snapshot_rows(cached)
            if len(rows) >= 100 and _age_ok(cached):
                cached = dict(cached)
                cached["rows"] = rows
                cached["row_count"] = len(rows)
                return cached

    snap = fetch_live_snapshot(require_live=True)
    if not snap.get("success") or len(snapshot_rows(snap)) < 100:
        snap = fetch_live_snapshot(require_live=False)

    rows = snapshot_rows(snap)
    if rows:
        snap = normalize_snapshot_for_persist(snap)
        persist_live_snapshot(snap)
        _SNAPSHOT_CACHE = (now, snap)
        try:
            import quant.application.screener_service as screener_mod

            screener_mod._LIVE_CACHE = None
        except Exception:
            pass
        return snap

    cached = _load_persisted_snapshot()
    if cached:
        stale_rows = snapshot_rows(cached)
        if stale_rows:
            cached = normalize_snapshot_for_persist(cached)
            cached["stale_fallback"] = True
            cached["success"] = True
            cached["blocked"] = False
            cached["rows"] = stale_rows
            cached["row_count"] = len(stale_rows)
            return cached
    out = dict(snap) if snap else {"success": False, "blocked": True}
    out.setdefault("blocked", True)
    out.setdefault("reason", "实时行情源不可用 — 无缓存可回退")
    return out


def live_price_map() -> dict[str, float]:
    """Symbol → latest price from persisted or fresh snapshot."""
    snap = ensure_live_quotes(refresh=False, max_age_sec=300)
    out: dict[str, float] = {}
    for row in snapshot_rows(snap):
        code = row.get("code")
        price = row.get("price")
        if code and price is not None:
            sym = normalize_ts_code(str(code))
            out[sym] = float(price)
    return out


# Back-compat alias
_normalize_ts_code = normalize_ts_code
