"""DataOS feature distribution drift — PSI / mean shift on screener factors."""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts"


def _psi(expected: list[float], actual: list[float], bins: int = 10) -> float:
    import math

    if len(expected) < 20 or len(actual) < 20:
        return 0.0
    lo = min(min(expected), min(actual))
    hi = max(max(expected), max(actual))
    if hi <= lo:
        return 0.0
    width = (hi - lo) / bins
    eps = 1e-6
    total = 0.0
    for i in range(bins):
        a_lo, a_hi = lo + i * width, lo + (i + 1) * width
        e_pct = sum(1 for x in expected if a_lo <= x < a_hi or (i == bins - 1 and x == a_hi)) / len(expected)
        a_pct = sum(1 for x in actual if a_lo <= x < a_hi or (i == bins - 1 and x == a_hi)) / len(actual)
        e_pct = max(e_pct, eps)
        a_pct = max(a_pct, eps)
        total += (a_pct - e_pct) * math.log(a_pct / e_pct)
    return abs(total)


def detect_feature_drift(*, lookback_days: int = 30, max_replay_dates: int = 8) -> dict[str, Any]:
    """Compare recent vs historical factor distributions from screener replay."""
    from quant.application.screener_service import get_screener_service

    wh = ROOT / "data" / "warehouse" / "quant.duckdb"
    if not wh.exists():
        return {"passed": False, "status": "NO_WAREHOUSE", "disable_live_trading": True}

    import duckdb

    con = duckdb.connect(str(wh), read_only=True)
    dates = [str(r[0]) for r in con.execute(
        "SELECT DISTINCT trade_date FROM daily_bars ORDER BY trade_date DESC LIMIT ?",
        [lookback_days],
    ).fetchall()]
    con.close()
    dates.reverse()
    if len(dates) < 10:
        return {"passed": True, "status": "INSUFFICIENT_HISTORY", "disable_live_trading": False}

    # Sample dates to keep closed-loop runtime bounded on laptop
    if len(dates) > max_replay_dates:
        step = max(1, len(dates) // max_replay_dates)
        dates = dates[::step][-max_replay_dates:]

    svc = get_screener_service()
    hist_vals: dict[str, list[float]] = {"ret_20": [], "vol_20": [], "trend": []}
    recent_vals: dict[str, list[float]] = {"ret_20": [], "vol_20": [], "trend": []}
    split = max(1, len(dates) - 2)
    for i, d in enumerate(dates):
        _, scored, _, bl = svc._score_universe(as_of_date=d, mode="eod", min_amount_cny=5e7, exclude_st=True)
        if bl or not scored:
            continue
        bucket = recent_vals if i >= split else hist_vals
        for r in scored[:200]:
            bucket["ret_20"].append(float(r.get("ret_20") or 0))
            bucket["vol_20"].append(float(r.get("vol_20") or 0))
            bucket["trend"].append(float(r.get("trend") or 0))

    drift_rows = []
    severe = False
    for feat in ("ret_20", "vol_20", "trend"):
        h, r = hist_vals[feat], recent_vals[feat]
        if len(h) < 30 or len(r) < 30:
            continue
        psi = round(_psi(h, r), 4)
        mean_shift = abs(statistics.fmean(r) - statistics.fmean(h))
        flagged = psi > 0.25 or mean_shift > 0.05
        if flagged:
            severe = True
        drift_rows.append({
            "feature": feat,
            "psi": psi,
            "mean_shift": round(mean_shift, 4),
            "passed": not flagged,
        })

    passed = not severe and bool(drift_rows)
    return {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "passed": passed,
        "status": "OK" if passed else "DRIFT_DETECTED",
        "disable_live_trading": severe,
        "features": drift_rows,
        "method": "PSI + mean_shift",
    }


def persist_drift_report(report: dict[str, Any] | None = None) -> Path:
    ART.mkdir(parents=True, exist_ok=True)
    report = report or detect_feature_drift()
    path = ART / "data_drift_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
