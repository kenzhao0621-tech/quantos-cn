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
    con.close()
    manifest = {"synced_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"), **stats}
    (WAREHOUSE_DIR / "sync_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def query(sql: str, params: Optional[list[Any]] = None) -> list[dict[str, Any]]:
    con = get_connection()
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    con.close()
    return rows
