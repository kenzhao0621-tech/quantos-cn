"""Data fetch — AKShare with fixture fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class MarketSnapshot:
    trade_date: str
    sh_index_close: Optional[float]
    sh_index_change_pct: Optional[float]
    sz_index_close: Optional[float]
    cyb_index_change_pct: Optional[float]
    data_timestamp: datetime
    source: str
    status: str
    advance_count: Optional[int] = None
    decline_count: Optional[int] = None


def load_fixture(name: str, fixtures_dir: Path) -> dict[str, Any]:
    path = fixtures_dir / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def snapshot_from_fixture(data: dict[str, Any]) -> MarketSnapshot:
    ts = datetime.fromisoformat(data["data_timestamp"])
    return MarketSnapshot(
        trade_date=data["trade_date"],
        sh_index_close=data.get("sh_index_close"),
        sh_index_change_pct=data.get("sh_index_change_pct"),
        sz_index_close=data.get("sz_index_close"),
        cyb_index_change_pct=data.get("cyb_index_change_pct"),
        data_timestamp=ts,
        source=data.get("source", "fixture"),
        status=data.get("status", "PREVIOUS_CLOSE"),
        advance_count=data.get("advance_count"),
        decline_count=data.get("decline_count"),
    )


def fetch_live_snapshot() -> MarketSnapshot:
    """Fetch via AKShare; raises on failure."""
    import akshare as ak

    now = datetime.now()
    # Index spot
    sh = ak.stock_zh_index_spot_em(symbol="上证指数")
    row = sh.iloc[0]
    sh_close = float(row["最新价"])
    sh_pct = float(row["涨跌幅"])
    sz = ak.stock_zh_index_spot_em(symbol="深证成指")
    sz_close = float(sz.iloc[0]["最新价"])
    cyb = ak.stock_zh_index_spot_em(symbol="创业板指")
    cyb_pct = float(cyb.iloc[0]["涨跌幅"])
    return MarketSnapshot(
        trade_date=now.strftime("%Y-%m-%d"),
        sh_index_close=sh_close,
        sh_index_change_pct=sh_pct,
        sz_index_close=sz_close,
        cyb_index_change_pct=cyb_pct,
        data_timestamp=now,
        source="akshare",
        status="DELAYED",
    )


def is_trading_day_akshare(d: str) -> bool:
    import akshare as ak

    cal = ak.tool_trade_date_hist_sina()
    return d in cal["trade_date"].astype(str).tolist()
