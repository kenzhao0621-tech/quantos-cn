"""MarketDataService — the single typed market-data boundary.

API routes and the portal BFF call this service only. They must never import
private provider functions (e.g. fetch_spot_snapshot) or touch DuckDB directly.

The default implementation reads the canonical DuckDB/Parquet warehouse so that
the market page always has data even without a live broker feed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from quant.domain.market_models import (
    DataMode,
    DatasetCoverage,
    DataRefreshJob,
    Freshness,
    IndexQuote,
    MarketOverview,
    ProviderHealth,
    ProviderStatusKind,
)

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"
INDEX_DIR = ROOT / "data" / "indices"

# Canonical index display names (CN A-share).
INDEX_NAMES: dict[str, str] = {
    "000001.SH": "上证综指",
    "000300.SH": "沪深300",
    "000852.SH": "中证1000",
    "000905.SH": "中证500",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
}


@runtime_checkable
class MarketDataService(Protocol):
    """Stable protocol — the contract enforced by contract tests."""

    def get_market_overview(self, *, mode: DataMode, run_id: str | None = None) -> MarketOverview: ...

    def refresh_market_data(self, *, datasets: list[str], mode: DataMode) -> DataRefreshJob: ...

    def get_provider_health(self) -> list[ProviderHealth]: ...

    def get_coverage(self) -> list[DatasetCoverage]: ...


class CanonicalMarketDataService:
    """Reads the canonical warehouse; degrades honestly when data is missing."""

    def __init__(self, warehouse: Path | None = None, index_dir: Path | None = None) -> None:
        self.warehouse = warehouse or WAREHOUSE
        self.index_dir = index_dir or INDEX_DIR

    # ---- internals -------------------------------------------------------
    def _connect(self):
        import duckdb

        return duckdb.connect(str(self.warehouse), read_only=True)

    def _index_quotes(self) -> tuple[list[IndexQuote], Optional[str]]:
        if not self.warehouse.exists():
            return [], None
        quotes: list[IndexQuote] = []
        as_of: Optional[str] = None
        try:
            con = self._connect()
            tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
            if "index_bars" not in tables:
                con.close()
                return [], None
            latest = con.execute("SELECT max(trade_date) FROM index_bars").fetchone()[0]
            as_of = str(latest) if latest else None
            rows = con.execute(
                """
                SELECT b.ts_code, b.close, b.vol, b.amount, b.trade_date,
                       p.close AS prev_close
                FROM index_bars b
                LEFT JOIN index_bars p
                  ON b.ts_code = p.ts_code
                 AND p.trade_date = (
                     SELECT max(trade_date) FROM index_bars x
                     WHERE x.ts_code = b.ts_code AND x.trade_date < b.trade_date
                 )
                WHERE b.trade_date = ?
                ORDER BY b.ts_code
                """,
                [latest],
            ).fetchall()
            con.close()
            for ts_code, close, vol, amount, td, prev_close in rows:
                pct = None
                if prev_close and prev_close != 0:
                    pct = round((close - prev_close) / prev_close * 100, 2)
                quotes.append(
                    IndexQuote(
                        symbol=ts_code,
                        name=INDEX_NAMES.get(ts_code, ts_code),
                        close=round(close, 2),
                        change_pct=pct,
                        volume=vol,
                        amount=amount,
                        trade_date=str(td),
                    )
                )
        except Exception:
            return [], as_of
        return quotes, as_of

    def _breadth(self, trade_date: Optional[str]) -> dict[str, int]:
        if not self.warehouse.exists() or not trade_date:
            return {}
        try:
            con = self._connect()
            tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
            if "daily_bars" not in tables:
                con.close()
                return {}
            latest = con.execute("SELECT max(trade_date) FROM daily_bars").fetchone()[0]
            row = con.execute(
                """
                SELECT
                  sum(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END),
                  sum(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END),
                  sum(CASE WHEN pct_chg = 0 THEN 1 ELSE 0 END),
                  count(*),
                  sum(CASE WHEN pct_chg >= 9.8 THEN 1 ELSE 0 END),
                  sum(CASE WHEN pct_chg <= -9.8 THEN 1 ELSE 0 END)
                FROM daily_bars WHERE trade_date = ?
                """,
                [latest],
            ).fetchone()
            con.close()
            adv, dec, unch, total, lu, ld = row
            return {
                "advancers": int(adv or 0),
                "decliners": int(dec or 0),
                "unchanged": int(unch or 0),
                "total_symbols": int(total or 0),
                "limit_up": int(lu or 0),
                "limit_down": int(ld or 0),
            }
        except Exception:
            return {}

    # ---- public API ------------------------------------------------------
    def get_market_overview(self, *, mode: DataMode, run_id: str | None = None) -> MarketOverview:
        if not self.warehouse.exists():
            return MarketOverview(
                mode=mode,
                freshness=Freshness.STALE,
                as_of_date=None,
                blocked=True,
                blocker_reason="规范化数据仓库不存在 — 请运行「更新数据」",
                blocker_dataset="warehouse",
                provenance={"warehouse": str(self.warehouse), "run_id": run_id},
            )
        indices, as_of = self._index_quotes()
        if not indices:
            return MarketOverview(
                mode=mode,
                freshness=Freshness.STALE,
                as_of_date=as_of,
                blocked=True,
                blocker_reason="指数数据集为空 — 请运行「更新数据」刷新 indices",
                blocker_dataset="index_bars",
                provenance={"warehouse": str(self.warehouse), "run_id": run_id},
            )
        breadth = self._breadth(as_of)
        freshness = Freshness.END_OF_DAY
        return MarketOverview(
            mode=mode,
            freshness=freshness,
            as_of_date=as_of,
            indices=indices,
            advancers=breadth.get("advancers", 0),
            decliners=breadth.get("decliners", 0),
            unchanged=breadth.get("unchanged", 0),
            total_symbols=breadth.get("total_symbols", 0),
            limit_up=breadth.get("limit_up", 0),
            limit_down=breadth.get("limit_down", 0),
            blocked=False,
            provenance={
                "warehouse": str(self.warehouse),
                "source": "canonical_duckdb",
                "run_id": run_id,
                "datasets": ["index_bars", "daily_bars"],
            },
        )

    def refresh_market_data(self, *, datasets: list[str], mode: DataMode) -> DataRefreshJob:
        from gateway.jobs.manager import get_job_manager

        jm = get_job_manager()
        job = jm.submit(
            job_type="market_refresh",
            payload={"datasets": datasets, "mode": mode.value},
        )
        return DataRefreshJob(job_id=job.job_id, datasets=datasets, mode=mode, status=job.status)

    def get_provider_health(self) -> list[ProviderHealth]:
        warehouse_ok = self.warehouse.exists()
        now = datetime.now(timezone.utc).isoformat()
        canonical = ProviderHealth(
            provider="canonical_warehouse",
            status=ProviderStatusKind.SUCCESS if warehouse_ok else ProviderStatusKind.NOT_CONFIGURED,
            datasets=["index_bars", "daily_bars", "disclosures", "features"],
            last_ok=now if warehouse_ok else None,
            detail="本地规范化 DuckDB/Parquet 仓库",
        )
        health = [canonical]
        # Live providers are not configured in this safe batch — report honestly.
        for name, datasets in (
            ("tushare", ["daily_bars", "indices"]),
            ("akshare_sina", ["spot_quotes", "indices"]),
            ("baostock", ["daily_bars"]),
            ("rqdata", ["live_spot"]),
            ("qmt_market_data", ["live_spot"]),
        ):
            health.append(
                ProviderHealth(
                    provider=name,
                    status=ProviderStatusKind.NOT_CONFIGURED,
                    datasets=datasets,
                    detail="未配置凭证 — 仅供日后授权后启用",
                )
            )
        return health

    def get_coverage(self) -> list[DatasetCoverage]:
        out: list[DatasetCoverage] = []
        if not self.warehouse.exists():
            return [DatasetCoverage("warehouse", 0, None, None, False, "warehouse missing")]
        try:
            con = self._connect()
            tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
            for ds in ("index_bars", "daily_bars", "disclosures", "features"):
                if ds not in tables:
                    out.append(DatasetCoverage(ds, 0, None, None, False, "table missing"))
                    continue
                cnt = con.execute(f"SELECT count(*) FROM {ds}").fetchone()[0]
                last_td = None
                if ds in ("index_bars", "daily_bars"):
                    last_td = con.execute(f"SELECT max(trade_date) FROM {ds}").fetchone()[0]
                    last_td = str(last_td) if last_td else None
                out.append(
                    DatasetCoverage(
                        dataset=ds,
                        row_count=int(cnt),
                        last_trade_date=last_td,
                        last_updated=None,
                        fresh=bool(cnt and cnt > 0),
                        blocker=None if cnt else "empty",
                    )
                )
            con.close()
        except Exception as exc:
            out.append(DatasetCoverage("warehouse", 0, None, None, False, str(exc)[:120]))
        return out


_service: Optional[CanonicalMarketDataService] = None


def get_market_data_service() -> CanonicalMarketDataService:
    global _service
    if _service is None:
        _service = CanonicalMarketDataService()
    return _service
