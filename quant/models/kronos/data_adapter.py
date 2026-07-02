"""KronosOS data adapter — warehouse OHLCV → sidecar bar payload."""

from __future__ import annotations

from typing import Any


def _adj_coverage_sufficient() -> bool:
    """Adjusted view is only trustworthy when adj factors cover ~all daily dates."""
    from quant.warehouse import query

    try:
        adj = int(query("SELECT count(DISTINCT trade_date) AS n FROM adj_factors")[0]["n"])
        daily = int(query("SELECT count(DISTINCT trade_date) AS n FROM daily_bars")[0]["n"])
        return daily > 0 and adj >= daily * 0.9
    except Exception:
        return False


def load_ohlcv_bars(symbol: str, *, lookback: int = 256, as_of_date: str | None = None) -> list[dict[str, Any]]:
    """Load real OHLCV bars from the warehouse (adjusted view when coverage allows)."""
    from quant.warehouse import query

    view = "daily_bars_adj" if _adj_coverage_sufficient() else "daily_bars"
    where_asof = "AND CAST(trade_date AS VARCHAR) <= ?" if as_of_date else ""
    params: list[Any] = [symbol]
    if as_of_date:
        params.append(as_of_date)
    params.append(lookback)

    rows = query(
        f"""
        SELECT CAST(trade_date AS VARCHAR) AS timestamp, open, high, low, close,
               vol AS volume, amount
        FROM {view}
        WHERE ts_code = ? {where_asof}
        ORDER BY trade_date DESC LIMIT ?
        """,
        params,
    )
    rows = [r for r in reversed(rows) if r.get("close")]
    return rows


def bars_are_adjusted() -> bool:
    return _adj_coverage_sufficient()
