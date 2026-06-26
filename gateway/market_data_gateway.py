"""Unified MarketDataGateway — stable facade over MarketDataFabric + warehouse.

All portal and strategy code should use this module for data tier labels,
health checks, and snapshot access. Never label EOD/DELAYED as REALTIME.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from gateway.config import ROOT
from gateway.market_status import get_market_status_summary

WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"
LIVE_SNAPSHOT = ROOT / "data" / "gateway" / "live_snapshot.json"


class DataTier(str, Enum):
    REALTIME = "REALTIME"
    DELAYED = "DELAYED"
    EOD = "EOD"
    SIMULATED = "SIMULATED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass
class DataQualityScore:
    tier: DataTier
    source: str
    updated_at: str
    delay_sec: int | None
    tradeable: bool
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier.value,
            "source": self.source,
            "updated_at": self.updated_at,
            "delay_sec": self.delay_sec,
            "tradeable": self.tradeable,
            "blockers": self.blockers,
        }


class MarketDataGateway:
    """SPEC-aligned gateway wrapping fabric + local caches."""

    def get_snapshot(self, symbols: list[str] | None = None) -> dict[str, Any]:
        live = self._load_live()
        rows = live.get("rows") or []
        if symbols:
            sym_set = set(symbols)
            rows = [r for r in rows if r.get("symbol") in sym_set or r.get("ts_code") in sym_set]
        tier = self._classify_live_tier(live)
        return {
            "tier": tier.value,
            "rows": rows,
            "row_count": len(rows),
            "provider": live.get("provider"),
            "updated_at": live.get("retrieved_at"),
            "tradeable": tier in (DataTier.REALTIME, DataTier.DELAYED) and not live.get("blocked"),
            "blocked": bool(live.get("blocked")),
            "reason": live.get("reason"),
        }

    def get_bars(
        self,
        symbols: list[str],
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        if not WAREHOUSE.exists():
            return {"tier": DataTier.UNKNOWN.value, "bars": [], "blockers": ["warehouse missing"]}
        import duckdb

        con = duckdb.connect(str(WAREHOUSE), read_only=True)
        ph = ",".join(["?"] * len(symbols)) if symbols else "?"
        params: list[Any] = list(symbols) if symbols else []
        where = f"ts_code IN ({ph})" if symbols else "1=1"
        if start:
            where += " AND trade_date >= ?"
            params.append(start)
        if end:
            where += " AND trade_date <= ?"
            params.append(end)
        rows = con.execute(
            f"SELECT ts_code, trade_date, open, high, low, close, pct_chg, amount FROM daily_bars WHERE {where} ORDER BY trade_date",
            params,
        ).fetchall()
        con.close()
        latest = max((str(r[1]) for r in rows), default="")
        return {
            "tier": DataTier.EOD.value,
            "bars": [
                {"symbol": r[0], "date": str(r[1]), "open": r[2], "high": r[3], "low": r[4], "close": r[5], "pct_chg": r[6], "amount": r[7]}
                for r in rows
            ],
            "as_of_date": latest,
            "tradeable": True,
        }

    def health(self, *, probe_live: bool = False) -> dict[str, Any]:
        summary = get_market_status_summary()
        live = summary.get("live") or {}
        wh = summary.get("warehouse") or {}
        tier = self._classify_live_tier(self._load_live()) if live.get("ok") else DataTier.EOD
        blockers: list[str] = []
        if not wh.get("ok"):
            blockers.append("WAREHOUSE_MISSING")
        if summary.get("needs_live_refresh"):
            blockers.append("LIVE_NOT_AVAILABLE")
        return {
            "status": "ok" if wh.get("ok") else "degraded",
            "eod_tier": DataTier.EOD.value,
            "live_tier": tier.value if live.get("ok") else DataTier.STALE.value,
            "warehouse_latest": wh.get("display_latest"),
            "live_ok": bool(live.get("ok")),
            "live_provider": live.get("provider"),
            "live_age_sec": live.get("age_sec"),
            "blockers": blockers,
            "labels": summary.get("labels"),
            "probe_live": probe_live,
        }

    def data_quality(self) -> DataQualityScore:
        live = self._load_live()
        tier = self._classify_live_tier(live)
        age = live.get("age_sec")
        blockers: list[str] = []
        if live.get("blocked"):
            blockers.append(str(live.get("reason") or "live_blocked"))
        tradeable = tier in (DataTier.REALTIME, DataTier.DELAYED, DataTier.EOD) and not blockers
        if tier == DataTier.STALE:
            tradeable = False
            blockers.append("data_stale")
        return DataQualityScore(
            tier=tier,
            source=str(live.get("provider") or "duckdb_eod"),
            updated_at=str(live.get("retrieved_at") or datetime.now(timezone.utc).isoformat()),
            delay_sec=int(age) if age is not None else None,
            tradeable=tradeable,
            blockers=blockers,
        )

    def _load_live(self) -> dict[str, Any]:
        if not LIVE_SNAPSHOT.exists():
            return {"blocked": True, "reason": "尚未刷新实时行情", "rows": []}
        try:
            return json.loads(LIVE_SNAPSHOT.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"blocked": True, "reason": str(exc)[:80], "rows": []}

    def _classify_live_tier(self, live: dict[str, Any]) -> DataTier:
        if live.get("blocked") or live.get("success") is False:
            return DataTier.STALE
        freshness = live.get("freshness")
        if isinstance(freshness, dict):
            label = str(freshness.get("label") or freshness.get("kind") or "").upper()
        else:
            label = str(freshness or "").upper()
        if "LICENSED" in label or "BROKER_REALTIME" in label:
            return DataTier.REALTIME
        if "DELAYED" in label or "INTRADAY" in label:
            return DataTier.DELAYED
        if live.get("is_live"):
            age = live.get("age_sec") or 0
            if age > 3600:
                return DataTier.STALE
            return DataTier.DELAYED
        if live.get("row_count", 0) > 0:
            return DataTier.DELAYED
        return DataTier.STALE


_gateway: MarketDataGateway | None = None


def get_market_data_gateway() -> MarketDataGateway:
    global _gateway
    if _gateway is None:
        _gateway = MarketDataGateway()
    return _gateway
