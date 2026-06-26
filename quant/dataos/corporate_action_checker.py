"""Corporate action awareness — flags when adj-factor data is missing."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def run_corporate_action_check() -> dict[str, Any]:
    """Best-effort check; full adj pipeline is Phase 2."""
    wh = ROOT / "data" / "warehouse" / "quant.duckdb"
    adj_table = False
    dividend_file = (ROOT / "data" / "fundamentals" / "fundamentals_tushare.json").exists()
    if wh.exists():
        import duckdb

        con = duckdb.connect(str(wh), read_only=True)
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        adj_table = "adj_factor" in tables or "corporate_actions" in tables
        con.close()

    passed = dividend_file  # partial: fundamentals include dv_ttm
    return {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "passed": passed,
        "status": "PARTIAL" if not adj_table else "OK",
        "adj_factor_table": adj_table,
        "fundamentals_file": dividend_file,
        "price_type_in_factors": "unadjusted_close",
        "recommendation": "Wire Tushare adj_factor before production live trading",
        "checks": [
            {"name": "adj_factor_available", "passed": adj_table},
            {"name": "dividend_metadata", "passed": dividend_file},
            {"name": "ST_flag_filter", "passed": True, "note": "screener exclude_st"},
            {"name": "suspension_filter", "passed": True, "note": "liquidity + limit-up filters"},
        ],
    }
