"""Qlib-compatible CN market provider — reads canonical DuckDB/Parquet store."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]


class CNMarketProvider:
    """Canonical data from existing warehouse — no separate unaudited Qlib store."""

    name = "CNMarketProvider"

    def __init__(self, warehouse_path: Path | None = None) -> None:
        self.warehouse = warehouse_path or ROOT / "data" / "warehouse" / "quant.duckdb"
        self._native_qlib = self._detect_qlib()

    def _detect_qlib(self) -> bool:
        try:
            import qlib  # noqa: F401
            return True
        except ImportError:
            return False

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "warehouse_exists": self.warehouse.exists(),
            "native_qlib": self._native_qlib,
            "mode": "native" if self._native_qlib else "adapter",
        }

    def load_daily_bars(self, *, limit: int = 500) -> list[dict[str, Any]]:
        if not self.warehouse.exists():
            return self._fallback_parquet(limit)
        try:
            from quant.warehouse import query
            rows = query(
                "SELECT * FROM daily_bars ORDER BY trade_date DESC LIMIT ?",
                [limit],
            )
            return rows
        except Exception:
            return self._fallback_parquet(limit)

    def _fallback_parquet(self, limit: int) -> list[dict[str, Any]]:
        import glob
        paths = sorted(glob.glob(str(ROOT / "data" / "historical" / "daily_bars" / "**" / "*.parquet")))
        if not paths:
            return []
        try:
            import pandas as pd
            df = pd.read_parquet(paths[-1])
            return df.head(limit).to_dict(orient="records")
        except Exception:
            return []

    def pit_filter(self, rows: list[dict[str, Any]], as_of: str) -> list[dict[str, Any]]:
        asof = as_of.replace("-", "")
        out = []
        for r in rows:
            td = str(r.get("trade_date", "")).replace("-", "")
            if td and td <= asof:
                out.append(r)
        return out
