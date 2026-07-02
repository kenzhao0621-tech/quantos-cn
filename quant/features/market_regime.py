"""FeatureOS — market regime features from index bars (trend / volatility / volume).

Consumed by the screener market-state overlay and the AgentsOS MarketRegimeAgent.
All values derive from the warehouse `index_bars` view (real data only); if the
benchmark index is missing the result is explicitly degraded.
"""

from __future__ import annotations

import statistics
from typing import Any

BENCHMARK_INDEX = "000300.SH"  # CSI 300
FALLBACK_INDICES = ("000001.SH", "000905.SH")


def _load_index_closes(ts_code: str, limit: int = 120) -> list[dict[str, Any]]:
    from quant.warehouse import query

    rows = query(
        "SELECT CAST(trade_date AS VARCHAR) AS trade_date, close, vol, amount "
        "FROM index_bars WHERE ts_code = ? ORDER BY trade_date DESC LIMIT ?",
        [ts_code, limit],
    )
    return list(reversed(rows))


def compute_market_regime(*, index_code: str | None = None, lookback: int = 120) -> dict[str, Any]:
    """Return regime label + score in [-1, 1] from real index bars."""
    candidates = [index_code] if index_code else [BENCHMARK_INDEX, *FALLBACK_INDICES]
    rows: list[dict[str, Any]] = []
    used = None
    for code in candidates:
        if not code:
            continue
        try:
            rows = _load_index_closes(code, lookback)
        except Exception:
            rows = []
        if len(rows) >= 40:
            used = code
            break
    if not used:
        return {
            "regime": "UNKNOWN",
            "score": 0.0,
            "degraded": True,
            "reason": "index_bars_insufficient",
        }

    closes = [float(r["close"]) for r in rows if r.get("close")]
    n = len(closes)
    ma20 = statistics.fmean(closes[-20:])
    ma60 = statistics.fmean(closes[-60:]) if n >= 60 else statistics.fmean(closes)
    last = closes[-1]
    rets = [(closes[i] / closes[i - 1] - 1) for i in range(1, n)]
    vol20 = statistics.pstdev(rets[-20:]) * (252 ** 0.5) if len(rets) >= 20 else 0.0
    ret20 = closes[-1] / closes[-21] - 1 if n >= 21 else 0.0

    trend_score = 0.0
    if last > ma20 > ma60:
        trend_score = 1.0
    elif last > ma20 or ma20 > ma60:
        trend_score = 0.4
    elif last < ma20 < ma60:
        trend_score = -1.0
    elif last < ma20 or ma20 < ma60:
        trend_score = -0.4

    # High annualised volatility (>30%) dampens conviction either way.
    vol_penalty = min(1.0, max(0.0, (vol20 - 0.20) / 0.20)) * 0.4
    score = max(-1.0, min(1.0, trend_score * (1.0 - vol_penalty)))

    if score >= 0.5:
        regime = "BULL_TREND"
    elif score >= 0.1:
        regime = "MILD_UP"
    elif score <= -0.5:
        regime = "BEAR_TREND"
    elif score <= -0.1:
        regime = "MILD_DOWN"
    else:
        regime = "RANGE_BOUND"

    return {
        "regime": regime,
        "score": round(score, 3),
        "index_code": used,
        "last_close": round(last, 2),
        "ma20": round(ma20, 2),
        "ma60": round(ma60, 2),
        "ret_20d_pct": round(ret20 * 100, 2),
        "annualized_vol_pct": round(vol20 * 100, 2),
        "bars_used": n,
        "degraded": False,
    }
