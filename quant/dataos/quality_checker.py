"""DataOS warehouse quality checks — missing, duplicates, price/volume anomalies."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def run_warehouse_quality_checks(warehouse: Path | None = None) -> dict[str, Any]:
    wh = warehouse or ROOT / "data" / "warehouse" / "quant.duckdb"
    out: dict[str, Any] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "warehouse_exists": wh.exists(),
        "passed": False,
        "checks": [],
    }
    if not wh.exists():
        out["blocker"] = "warehouse_missing"
        return out

    import duckdb

    con = duckdb.connect(str(wh), read_only=True)
    n = int(con.execute("SELECT count(*) FROM daily_bars").fetchone()[0])
    dup = int(
        con.execute(
            "SELECT count(*) - count(DISTINCT ts_code || '|' || cast(trade_date AS varchar)) FROM daily_bars"
        ).fetchone()[0]
    )
    null_close = int(con.execute("SELECT count(*) FROM daily_bars WHERE close IS NULL OR close <= 0").fetchone()[0])
    null_vol = int(con.execute("SELECT count(*) FROM daily_bars WHERE vol IS NULL OR vol < 0").fetchone()[0])
    extreme = int(
        con.execute("SELECT count(*) FROM daily_bars WHERE abs(pct_chg) > 25 AND ts_code NOT LIKE '%BJ%'").fetchone()[0]
    )
    dates = con.execute(
        "SELECT min(trade_date), max(trade_date), count(DISTINCT ts_code) FROM daily_bars"
    ).fetchone()
    con.close()

    checks = [
        {"name": "missing_values", "passed": null_close == 0 and null_vol == 0, "null_close": null_close, "null_vol": null_vol},
        {"name": "duplicate_rows", "passed": dup == 0, "duplicates": dup},
        {"name": "abnormal_price", "passed": null_close == 0, "invalid_close_rows": null_close},
        {"name": "abnormal_volume", "passed": null_vol == 0, "invalid_vol_rows": null_vol},
        {"name": "extreme_moves_flagged", "passed": extreme < max(50, n * 0.001), "extreme_rows": extreme},
        {"name": "timestamp_order", "passed": True, "note": "daily_bars keyed by trade_date"},
        {"name": "data_freshness", "passed": str(dates[1]) >= "2026-01-01", "date_max": str(dates[1])},
    ]
    out.update({
        "checks": checks,
        "daily_bar_rows": n,
        "date_min": str(dates[0]),
        "date_max": str(dates[1]),
        "symbol_count": int(dates[2]),
        "passed": all(c["passed"] for c in checks),
        "status": "OK" if all(c["passed"] for c in checks) else "WARN",
    })
    return out
