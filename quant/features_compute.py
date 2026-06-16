"""Compute and persist technical features from warehouse daily bars."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FEATURE_ROOT = ROOT / "data" / "parquet" / "features"
FORMULA_VERSION = "features_v1"


def _code_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def build_feature_store(*, sample_codes: int = 200) -> dict[str, Any]:
    """Compute features for a sample of liquid names from latest partitions."""
    try:
        import duckdb
        import pandas as pd
    except ImportError as e:
        return {"error": str(e), "built": False}

    from quant.warehouse import sync_from_partitions

    sync_from_partitions()
    hist_glob = str(ROOT / "data" / "historical" / "daily_bars" / "**" / "*.parquet")
    con = duckdb.connect()
    try:
        df = con.execute(
            """
            SELECT ts_code, trade_date, open, high, low, close, vol, amount
            FROM read_parquet(?, union_by_name=true)
            WHERE ts_code IS NOT NULL
            ORDER BY ts_code, trade_date
            """,
            [hist_glob],
        ).fetchdf()
    except Exception as e:
        con.close()
        return {"error": f"no daily bars: {e}", "built": False}
    con.close()

    if df.empty:
        return {"error": "empty daily bars", "built": False}

    if "ts_code" not in df.columns and "symbol" in df.columns:
        df["ts_code"] = df["symbol"]
    for col in ("open", "high", "low", "close", "vol"):
        if col not in df.columns:
            df[col] = 0.0

    codes = df["ts_code"].value_counts().head(sample_codes).index.tolist()
    out_rows: list[dict[str, Any]] = []
    commit = _code_commit()
    market_date = str(df["trade_date"].max())

    for code in codes:
        sub = df[df["ts_code"] == code].sort_values("trade_date")
        if len(sub) < 20:
            continue
        c = sub["close"].astype(float)
        v = sub["vol"].astype(float)
        ret5 = (c.iloc[-1] / c.iloc[-6] - 1) * 100 if len(c) >= 6 else 0
        ret20 = (c.iloc[-1] / c.iloc[-21] - 1) * 100 if len(c) >= 21 else 0
        ret60 = (c.iloc[-1] / c.iloc[-61] - 1) * 100 if len(c) >= 61 else 0
        ma20 = c.tail(20).mean()
        vol20 = c.pct_change().tail(20).std() * 100
        dd20 = ((c.tail(20) / c.tail(20).cummax()) - 1).min() * 100
        amt20 = (sub["amount"].astype(float).tail(20).mean() if "amount" in sub else v.tail(20).mean())
        out_rows.append({
            "code": code,
            "market_date": market_date,
            "ma5": round(c.tail(5).mean(), 4),
            "ma20": round(ma20, 4),
            "ma60": round(c.tail(60).mean(), 4) if len(c) >= 60 else None,
            "ret_5d": round(ret5, 4),
            "ret_20d": round(ret20, 4),
            "ret_60d": round(ret60, 4),
            "volatility_20d": round(vol20, 4),
            "max_drawdown_20d": round(dd20, 4),
            "avg_amount_20d": round(float(amt20), 2),
            "formula_version": FORMULA_VERSION,
            "code_commit": commit,
        })

    FEATURE_ROOT.mkdir(parents=True, exist_ok=True)
    path = FEATURE_ROOT / f"trade_date={market_date}" / "features.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = pd.DataFrame(out_rows)
    pdf.to_parquet(path, index=False)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    summary = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "market_date": market_date,
        "row_count": len(out_rows),
        "path": str(path.relative_to(ROOT)),
        "sha256": sha,
        "formula_version": FORMULA_VERSION,
        "code_commit": commit,
    }
    (ROOT / "data" / "features" / "feature_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
