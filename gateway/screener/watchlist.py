"""User screener watchlist / favorites with optional broker sync."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT

WATCHLIST_PATH = ROOT / "data" / "gateway" / "screener_watchlist.json"


def _load_all() -> dict[str, Any]:
    if not WATCHLIST_PATH.exists():
        return {"users": {}}
    return json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))


def _save_all(data: dict[str, Any]) -> None:
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_watchlist(user_id: str) -> list[dict[str, Any]]:
    data = _load_all()
    return list(data.get("users", {}).get(user_id, {}).get("items", []))


def add_to_watchlist(
    user_id: str,
    *,
    symbol: str,
    name: str = "",
    notes: str = "",
    source: str = "screener",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = _load_all()
    users = data.setdefault("users", {})
    bucket = users.setdefault(user_id, {"items": []})
    items: list[dict[str, Any]] = bucket.setdefault("items", [])
    sym = symbol.strip().upper()
    for it in items:
        if it.get("symbol") == sym:
            it.update({
                "name": name or it.get("name", ""),
                "notes": notes or it.get("notes", ""),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            _save_all(data)
            return it
    entry = {
        "symbol": sym,
        "name": name,
        "notes": notes,
        "source": source,
        "meta": meta or {},
        "added_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "broker_synced": False,
    }
    items.append(entry)
    _save_all(data)
    return entry


def remove_from_watchlist(user_id: str, symbol: str) -> bool:
    data = _load_all()
    items = data.get("users", {}).get(user_id, {}).get("items", [])
    sym = symbol.strip().upper()
    new_items = [i for i in items if i.get("symbol") != sym]
    if len(new_items) == len(items):
        return False
    data.setdefault("users", {}).setdefault(user_id, {})["items"] = new_items
    _save_all(data)
    return True


def mark_items_synced(user_id: str, symbols: list[str]) -> int:
    """Mark watchlist items as broker-synced."""
    if not symbols:
        return 0
    sym_set = {s.strip().upper() for s in symbols}
    data = _load_all()
    count = 0
    for it in data.get("users", {}).get(user_id, {}).get("items", []):
        if it.get("symbol") in sym_set:
            it["broker_synced"] = True
            it["broker_synced_at"] = datetime.now(timezone.utc).isoformat()
            count += 1
    _save_all(data)
    return count


def sync_watchlist_to_broker(user_id: str) -> dict[str, Any]:
    """Export favorites for QMT watchlist file or Eastmoney manual import."""
    from gateway.brokers.connection_manager import load_broker_config, test_broker_connection

    items = list_watchlist(user_id)
    if not items:
        return {"ok": False, "error": "EMPTY_WATCHLIST", "message": "收藏列表为空"}
    cfg = load_broker_config()
    conn = test_broker_connection(cfg)
    lines = [f"{it['symbol'].split('.')[0]},{it.get('name', '')}" for it in items]
    result: dict[str, Any] = {"ok": True, "count": len(items), "broker": cfg.active_broker}

    if cfg.active_broker == "qmt_local" and conn.get("connected"):
        drop = Path(cfg.qmt_order_dir).expanduser()
        watch_dir = drop.parent / "watchlist"
        watch_dir.mkdir(parents=True, exist_ok=True)
        path = watch_dir / "quantos_watchlist.csv"
        path.write_text("证券代码,证券名称\n" + "\n".join(lines), encoding="utf-8-sig")
        result["mode"] = "qmt_watchlist_csv"
        result["file"] = str(path)
        result["message"] = f"已写入 QMT 自选股文件 {path}，请在 MiniQMT 导入或刷新自选股。"
    elif cfg.active_broker == "eastmoney_manual":
        result["mode"] = "eastmoney_manual"
        result["steps"] = [
            "打开东方财富 App → 自选股 → 添加",
            *[f"添加 {it.get('name') or it['symbol']}（{it['symbol']}）" for it in items[:20]],
            "保存后可在 App 内设置价格提醒与条件单",
        ]
        result["portal_url"] = "https://www.18.cn/"
    else:
        result["ok"] = False
        result["error"] = "BROKER_NOT_CONFIGURED"
        result["message"] = "请先在券商页配置 QMT 或东方财富并测试连接"

    if result.get("ok"):
        data = _load_all()
        for it in data.get("users", {}).get(user_id, {}).get("items", []):
            it["broker_synced"] = True
            it["broker_synced_at"] = datetime.now(timezone.utc).isoformat()
        _save_all(data)
    return result
