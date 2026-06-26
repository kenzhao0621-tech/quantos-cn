"""Build and load Alpha158 wide parquet cache."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "parquet" / "features" / "alpha158"
WIDE_PATH = CACHE_DIR / "alpha158_wide.parquet"
MANIFEST_PATH = ROOT / "artifacts" / "alpha158_cache_manifest.json"


def _load_bars_from_warehouse(*, symbols: list[str] | None = None, lookback_days: int = 800) -> pd.DataFrame:
    wh = ROOT / "data" / "warehouse" / "quant.duckdb"
    if not wh.exists():
        raise FileNotFoundError("warehouse missing — run data sync first")
    import duckdb

    con = duckdb.connect(str(wh), read_only=True)
    if symbols:
        ph = ",".join(["?"] * len(symbols))
        q = f"""
        SELECT ts_code, trade_date, open, high, low, close, vol, amount, pct_chg
        FROM daily_bars
        WHERE ts_code IN ({ph})
          AND trade_date >= (SELECT max(trade_date) FROM daily_bars) - INTERVAL '{lookback_days} days'
        ORDER BY ts_code, trade_date
        """
        df = con.execute(q, symbols).fetchdf()
    else:
        q = f"""
        SELECT ts_code, trade_date, open, high, low, close, vol, amount, pct_chg
        FROM daily_bars
        WHERE trade_date >= (SELECT max(trade_date) FROM daily_bars) - INTERVAL '{lookback_days} days'
        ORDER BY ts_code, trade_date
        """
        df = con.execute(q).fetchdf()
    con.close()
    return df


def sample_universe_csi300_proxy(n: int = 300) -> list[str]:
    """Top-N liquid names as CSI300 proxy when constituent file unavailable."""
    wh = ROOT / "data" / "warehouse" / "quant.duckdb"
    import duckdb

    con = duckdb.connect(str(wh), read_only=True)
    rows = con.execute(
        """
        WITH recent AS (
          SELECT ts_code, avg(amount) AS avg_amt
          FROM daily_bars
          WHERE trade_date >= (SELECT max(trade_date) FROM daily_bars) - INTERVAL '30 days'
          GROUP BY ts_code
        )
        SELECT ts_code FROM recent
        WHERE ts_code NOT LIKE '%.BJ'
        ORDER BY avg_amt DESC
        LIMIT ?
        """,
        [n],
    ).fetchall()
    con.close()
    return [str(r[0]) for r in rows]


def build_alpha158_cache(
    *,
    mode: str = "sample",
    sample_size: int = 300,
    lookback_days: int = 800,
    force: bool = False,
) -> dict[str, Any]:
    """Build wide Alpha158 parquet. mode: sample | full."""
    from quant.features.alpha158 import FEATURE_VERSION, compute_alpha158_frame, feature_column_names

    if WIDE_PATH.exists() and not force:
        return load_manifest()

    symbols = sample_universe_csi300_proxy(sample_size) if mode == "sample" else None
    bars = _load_bars_from_warehouse(symbols=symbols, lookback_days=lookback_days)
    if bars.empty:
        return {"built": False, "error": "no bars"}

    wide = compute_alpha158_frame(bars)
    if wide.empty:
        return {"built": False, "error": "no features computed"}

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wide.to_parquet(WIDE_PATH, index=False)
    sha = hashlib.sha256(WIDE_PATH.read_bytes()).hexdigest()
    manifest = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "built": True,
        "mode": mode,
        "feature_version": FEATURE_VERSION,
        "n_features": len(feature_column_names()),
        "feature_columns": feature_column_names(),
        "n_rows": len(wide),
        "n_symbols": int(wide["ts_code"].nunique()),
        "date_min": str(wide["trade_date"].min()),
        "date_max": str(wide["trade_date"].max()),
        "path": str(WIDE_PATH.relative_to(ROOT)),
        "sha256": sha,
        "symbols": symbols[:10] if symbols else "full_universe",
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def load_alpha158_wide() -> pd.DataFrame:
    if not WIDE_PATH.exists():
        build_alpha158_cache(mode="sample")
    return pd.read_parquet(WIDE_PATH)


def load_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if WIDE_PATH.exists():
        return {"built": True, "path": str(WIDE_PATH.relative_to(ROOT)), "from_file_only": True}
    return {"built": False}
