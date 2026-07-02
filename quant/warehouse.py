"""DuckDB warehouse over Parquet/JSON quant datasets — SQL-only numerics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_DIR = ROOT / "data" / "warehouse"
DUCKDB_PATH = WAREHOUSE_DIR / "quant.duckdb"
PARQUET_ROOT = ROOT / "data" / "parquet"


def ensure_layout() -> None:
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    PARQUET_ROOT.mkdir(parents=True, exist_ok=True)
    for sub in ("daily_bars", "indices", "sectors", "fundamentals", "disclosures", "features"):
        (PARQUET_ROOT / sub).mkdir(parents=True, exist_ok=True)


def get_connection():
    import duckdb

    ensure_layout()
    con = duckdb.connect(str(DUCKDB_PATH))
    return con


def sync_from_partitions(*, run_id: str = "") -> dict[str, Any]:
    """Register Parquet globs into DuckDB views."""
    ensure_layout()
    con = get_connection()
    hist_glob = str(ROOT / "data" / "historical" / "daily_bars" / "**" / "*.parquet")
    idx_glob = str(PARQUET_ROOT / "indices" / "*.parquet")
    feat_glob = str(PARQUET_ROOT / "features" / "**" / "*.parquet")

    # DuckDB does not allow prepared parameters in CREATE VIEW bodies,
    # so we embed the glob directly into the SQL string.
    daily_sql = (
        "CREATE OR REPLACE VIEW daily_bars AS "
        f"SELECT * FROM read_parquet('{hist_glob}', union_by_name=true)"
    )
    con.execute(daily_sql)
    try:
        idx_sql = (
            "CREATE OR REPLACE VIEW index_bars AS "
            f"SELECT * FROM read_parquet('{idx_glob}', union_by_name=true)"
        )
        con.execute(idx_sql)
    except Exception:
        con.execute("CREATE OR REPLACE VIEW index_bars AS SELECT NULL::VARCHAR ts_code WHERE false")
    try:
        feat_sql = (
            "CREATE OR REPLACE VIEW features AS "
            f"SELECT * FROM read_parquet('{feat_glob}', union_by_name=true)"
        )
        con.execute(feat_sql)
    except Exception:
        con.execute("CREATE OR REPLACE VIEW features AS SELECT NULL::VARCHAR code WHERE false")

    # trade_calendar view.
    cal_path = PARQUET_ROOT / "calendar" / "trade_calendar.parquet"
    try:
        if cal_path.exists():
            con.execute(
                "CREATE OR REPLACE VIEW trade_calendar AS "
                f"SELECT * FROM read_parquet('{cal_path}')"
            )
        else:
            raise FileNotFoundError(str(cal_path))
    except Exception:
        con.execute("CREATE OR REPLACE VIEW trade_calendar AS SELECT NULL::VARCHAR cal_date, NULL::INTEGER is_open WHERE false")

    # adj_factors + forward-adjusted (前复权) daily bars.
    adj_glob = str(PARQUET_ROOT / "adj_factors" / "*.parquet")
    try:
        if list((PARQUET_ROOT / "adj_factors").glob("*.parquet")):
            con.execute(
                "CREATE OR REPLACE VIEW adj_factors AS "
                f"SELECT * FROM read_parquet('{adj_glob}', union_by_name=true)"
            )
            con.execute(
                "CREATE OR REPLACE VIEW daily_bars_adj AS "
                "WITH latest AS (SELECT ts_code, adj_factor AS latest_factor FROM ("
                "  SELECT ts_code, adj_factor, ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) rn"
                "  FROM adj_factors) WHERE rn = 1) "
                "SELECT b.ts_code, b.trade_date, "
                "b.open * a.adj_factor / l.latest_factor AS open, "
                "b.high * a.adj_factor / l.latest_factor AS high, "
                "b.low * a.adj_factor / l.latest_factor AS low, "
                "b.close * a.adj_factor / l.latest_factor AS close, "
                "b.vol, b.amount, b.pct_chg, a.adj_factor "
                "FROM daily_bars b "
                "JOIN adj_factors a ON b.ts_code = a.ts_code "
                "AND replace(CAST(b.trade_date AS VARCHAR), '-', '') = replace(CAST(a.trade_date AS VARCHAR), '-', '') "
                "JOIN latest l ON b.ts_code = l.ts_code"
            )
        else:
            raise FileNotFoundError(adj_glob)
    except Exception:
        con.execute("CREATE OR REPLACE VIEW adj_factors AS SELECT NULL::VARCHAR ts_code WHERE false")
        con.execute("CREATE OR REPLACE VIEW daily_bars_adj AS SELECT * FROM daily_bars")

    # industry_map / fundamental views over JSON sidecars (refactor audit §5.2:
    # sectors/fundamentals previously lived outside the warehouse).
    sectors_json = str(ROOT / "data" / "sectors" / "sector_boards_tushare.json")
    fund_json = str(ROOT / "data" / "fundamentals" / "fundamentals_tushare.json")
    try:
        if Path(sectors_json).exists():
            con.execute(
                "CREATE OR REPLACE VIEW industry_map AS "
                "SELECT unnest.code AS code, unnest.name AS name, "
                "unnest.sector_code AS sector_code, unnest.sector_name AS sector_name, "
                "unnest.provider AS source "
                f"FROM (SELECT unnest(rows) AS unnest FROM read_json_auto('{sectors_json}'))"
            )
        else:
            raise FileNotFoundError(sectors_json)
    except Exception:
        con.execute("CREATE OR REPLACE VIEW industry_map AS SELECT NULL::VARCHAR code WHERE false")
    try:
        if Path(fund_json).exists():
            con.execute(
                "CREATE OR REPLACE VIEW fundamental AS "
                "SELECT unnest.ts_code AS ts_code, unnest.trade_date AS trade_date, "
                "unnest.pe AS pe_ttm, unnest.pb AS pb, unnest.ps AS ps, "
                "unnest.turnover_rate AS turnover_rate, unnest.dv_ttm AS dv_ttm, "
                "unnest.total_mv AS total_mv, unnest.circ_mv AS circ_mv, "
                "unnest.provider AS source "
                f"FROM (SELECT unnest(rows) AS unnest FROM read_json_auto('{fund_json}'))"
            )
        else:
            raise FileNotFoundError(fund_json)
    except Exception:
        con.execute("CREATE OR REPLACE VIEW fundamental AS SELECT NULL::VARCHAR ts_code WHERE false")

    stats: dict[str, Any] = {"duckdb": str(DUCKDB_PATH.relative_to(ROOT)), "run_id": run_id}
    try:
        stats["daily_bar_rows"] = int(con.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0])
        stats["daily_trade_dates"] = int(con.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bars").fetchone()[0])
    except Exception as e:
        stats["daily_bar_error"] = str(e)
    try:
        stats["index_rows"] = int(con.execute("SELECT COUNT(*) FROM index_bars").fetchone()[0])
    except Exception:
        stats["index_rows"] = 0
    for view in ("industry_map", "fundamental"):
        try:
            stats[f"{view}_rows"] = int(con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0])
        except Exception:
            stats[f"{view}_rows"] = 0
    con.close()
    manifest = {"synced_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"), **stats}
    (WAREHOUSE_DIR / "sync_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def query(sql: str, params: Optional[list[Any]] = None) -> list[dict[str, Any]]:
    import duckdb

    ensure_layout()
    # Read-only connection: avoids write-lock contention with backfill jobs.
    try:
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    except Exception:
        con = get_connection()
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    con.close()
    return rows
