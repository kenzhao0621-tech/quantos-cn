"""ResearchOS data panel — liquid-universe close/return matrix from the warehouse.

One SQL load, then all research trials evaluate in-memory. Real data only;
insufficient data returns an explicitly degraded panel.
"""

from __future__ import annotations

from typing import Any


def load_research_panel(*, max_symbols: int = 300, min_days: int = 40) -> dict[str, Any]:
    """Return {dates, symbols, closes{sym: [close..]}, pct{sym: [pct..]}} aligned by date."""
    from quant.warehouse import query

    # Most liquid symbols by mean amount over the full window (main boards only).
    symbols = [
        r["ts_code"] for r in query(
            """
            SELECT ts_code, avg(amount) AS mean_amount
            FROM daily_bars
            WHERE (ts_code LIKE '60%' OR ts_code LIKE '00%')
            GROUP BY ts_code
            HAVING count(*) >= ?
            ORDER BY mean_amount DESC
            LIMIT ?
            """,
            [min_days, max_symbols],
        )
    ]
    if not symbols:
        return {"ok": False, "degraded": True, "reason": "no_liquid_universe"}

    ph = ",".join(["?"] * len(symbols))
    rows = query(
        f"""
        SELECT ts_code, CAST(trade_date AS VARCHAR) AS d, close, pct_chg, vol
        FROM daily_bars
        WHERE ts_code IN ({ph})
        ORDER BY trade_date
        """,
        symbols,
    )
    all_dates = sorted({r["d"] for r in rows})
    dates = _contiguous_tail(all_dates)
    dropped = len(all_dates) - len(dates)
    if dropped:
        cutoff = dates[0]
        rows = [r for r in rows if r["d"] >= cutoff]
    date_idx = {d: i for i, d in enumerate(dates)}
    closes: dict[str, list] = {s: [None] * len(dates) for s in symbols}
    pct: dict[str, list] = {s: [None] * len(dates) for s in symbols}
    vol: dict[str, list] = {s: [None] * len(dates) for s in symbols}
    for r in rows:
        i = date_idx[r["d"]]
        s = r["ts_code"]
        closes[s][i] = float(r["close"]) if r["close"] else None
        pct[s][i] = float(r["pct_chg"]) if r["pct_chg"] is not None else None
        vol[s][i] = float(r["vol"]) if r["vol"] is not None else None

    return {
        "ok": True,
        "degraded": dropped > 0,
        "degraded_reason": f"non_contiguous_history_dropped:{dropped}_dates" if dropped else "",
        "dates": dates,
        "symbols": symbols,
        "closes": closes,
        "pct": pct,
        "vol": vol,
        "window": {"start": dates[0], "end": dates[-1], "days": len(dates)},
    }


def _contiguous_tail(dates: list[str], *, max_gap_days: int = 20) -> list[str]:
    """Trim to the most recent contiguous stretch (no calendar gaps > max_gap_days).

    The warehouse may contain non-contiguous historical islands while a backfill
    is in progress; simulating across a gap would fabricate multi-month returns
    as if they were one day.
    """
    from datetime import date

    if len(dates) < 2:
        return dates
    parsed = [date.fromisoformat(d[:10]) for d in dates]
    start = 0
    for i in range(1, len(parsed)):
        if (parsed[i] - parsed[i - 1]).days > max_gap_days:
            start = i
    return dates[start:]
