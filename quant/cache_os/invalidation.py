"""Underlying-data-change invalidation (v2.2 §3.3 feature_vector, §4.1 DAG rule).

The rule "如果底层数据没变，不要重算" is implemented by fingerprinting the
underlying dataset and embedding the fingerprint in the cache key's
``as_of_date``/params. When the fingerprint changes the key changes, so stale
entries are simply never hit again; no explicit deletion is required. This
module provides the fingerprint helpers.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"


def warehouse_data_version(
    *,
    table: str = "daily_bars",
    symbol: Optional[str] = None,
    warehouse: Optional[Path] = None,
) -> str:
    """Cheap fingerprint of a warehouse table: (max trade_date, row count).

    O(1) on DuckDB zone maps — safe to call per request. Returns
    "unavailable" when the warehouse is missing so callers can degrade.
    """
    wh = warehouse or WAREHOUSE
    if not wh.exists():
        return "unavailable"
    try:
        import duckdb

        con = duckdb.connect(str(wh), read_only=True)
        try:
            if symbol:
                row = con.execute(
                    f"SELECT max(trade_date), count(*) FROM {table} WHERE ts_code = ?",
                    [symbol],
                ).fetchone()
            else:
                row = con.execute(f"SELECT max(trade_date), count(*) FROM {table}").fetchone()
        finally:
            con.close()
        max_date, count = row or (None, 0)
        if not max_date:
            return "empty"
        return f"{max_date}:{count}"
    except Exception:
        return "unavailable"


def file_data_version(path: Path) -> str:
    """Fingerprint of a file-backed dataset (live snapshot JSON etc.)."""
    if not path.exists():
        return "unavailable"
    stat = path.stat()
    return hashlib.sha256(f"{stat.st_mtime_ns}:{stat.st_size}".encode()).hexdigest()[:16]
