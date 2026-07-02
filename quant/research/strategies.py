"""ResearchOS strategy evaluation — baselines + parameterised momentum ranker.

All strategies simulate T+1 daily portfolios on the shared panel with A-share
realism: limit-up entries blocked, suspended (vol=0) names not entered, costs +
slippage charged once per round trip on rebalance days (not every day — daily
charging would systematically punish low-turnover strategies).
"""

from __future__ import annotations

import statistics
from typing import Any

COST_BPS = 8.0
SLIPPAGE_BPS = 12.0
ROUND_TRIP_PCT = (COST_BPS + SLIPPAGE_BPS) / 100.0
LIMIT_ENTRY_PCT = 9.7


def _enterable(panel: dict[str, Any], sym: str, i: int) -> bool:
    """Can we enter at close of day i? Not suspended, not at limit-up."""
    v = panel["vol"][sym][i]
    p = panel["pct"][sym][i]
    return v is not None and v > 0 and (p is None or p < LIMIT_ENTRY_PCT)


def _daily_gross(panel: dict[str, Any], picks: list[str], d: int) -> float | None:
    """Equal-weight gross portfolio return (pct) close d -> close d+1.

    Suspended/missing bars contribute 0 (position frozen), matching A-share
    reality where a suspended holding cannot be traded.
    """
    rets: list[float] = []
    for sym in picks:
        closes = panel["closes"][sym]
        if d + 1 < len(closes) and closes[d] and closes[d + 1]:
            rets.append((closes[d + 1] / closes[d] - 1.0) * 100.0)
        else:
            rets.append(0.0)
    return statistics.fmean(rets) if rets else None


def _run_periodic_portfolio(panel: dict[str, Any], pick_fn, *, start: int,
                            hold: int = 5, top_k: int = 10) -> list[float]:
    """Generic engine: re-pick every `hold` days, charge one round trip per rebalance."""
    dates = panel["dates"]
    daily: list[float] = []
    i = start
    while i < len(dates) - 1:
        scores = pick_fn(i)
        if len(scores) < top_k:
            i += hold
            continue
        picks = [sym for _, sym in scores[:top_k]]
        period_end = min(i + hold, len(dates) - 1)
        cost_per_day = ROUND_TRIP_PCT / max(1, period_end - i)
        for d in range(i, period_end):
            g = _daily_gross(panel, picks, d)
            if g is not None:
                daily.append(g - cost_per_day)
        i = period_end
    return daily


def momentum_rank_strategy(panel: dict[str, Any], *, window: int = 20, top_k: int = 10,
                           vol_penalty: float = 0.0, reverse: bool = False,
                           hold: int = 5) -> list[float]:
    """Rank-based momentum (or reversal with reverse=True), periodic rebalance."""

    def pick(i: int) -> list[tuple[float, str]]:
        scores: list[tuple[float, str]] = []
        for sym in panel["symbols"]:
            closes = panel["closes"][sym]
            if i < window or not closes[i] or not closes[i - window]:
                continue
            if not _enterable(panel, sym, i):
                continue
            mom = closes[i] / closes[i - window] - 1.0
            if vol_penalty > 0:
                rets = [
                    (closes[j] / closes[j - 1] - 1.0)
                    for j in range(max(1, i - 19), i + 1)
                    if closes[j] and closes[j - 1]
                ]
                vol = statistics.pstdev(rets) if len(rets) > 2 else 0.0
                mom -= vol_penalty * vol * 10
            scores.append((mom, sym))
        scores.sort(reverse=not reverse)
        return scores

    return _run_periodic_portfolio(panel, pick, start=window, hold=hold, top_k=top_k)


def ma_crossover_strategy(panel: dict[str, Any], *, fast: int = 5, slow: int = 20,
                          top_k: int = 10, hold: int = 5) -> list[float]:
    """Hold names whose fast MA is above slow MA, ranked by cross strength."""

    def pick(i: int) -> list[tuple[float, str]]:
        scores: list[tuple[float, str]] = []
        for sym in panel["symbols"]:
            closes = panel["closes"][sym]
            if i < slow:
                continue
            win = closes[i - slow + 1: i + 1]
            if any(c is None for c in win) or not _enterable(panel, sym, i):
                continue
            ma_fast = statistics.fmean(win[-fast:])
            ma_slow = statistics.fmean(win)
            if ma_fast > ma_slow:
                scores.append((ma_fast / ma_slow - 1.0, sym))
        scores.sort(reverse=True)
        return scores

    return _run_periodic_portfolio(panel, pick, start=slow, hold=hold, top_k=top_k)


def equal_weight_topk_liquidity(panel: dict[str, Any], *, top_k: int = 50) -> list[float]:
    """Passive: buy the top-k most liquid names once, hold the whole window."""
    picks = panel["symbols"][:top_k]
    dates = panel["dates"]
    daily: list[float] = []
    for d in range(len(dates) - 1):
        g = _daily_gross(panel, picks, d)
        if g is not None:
            daily.append(g)
    if daily:
        daily[0] -= ROUND_TRIP_PCT  # single round trip over the window
    return daily


def index_buy_hold_daily(*, start: str | None = None, end: str | None = None) -> tuple[list[float], dict[str, Any]]:
    """CSI300 daily pct series aligned to [start, end] (no costs — passive benchmark)."""
    from quant.warehouse import query

    rows = query(
        """
        SELECT CAST(trade_date AS VARCHAR) AS d, close
        FROM index_bars WHERE ts_code = '000300.SH' ORDER BY trade_date
        """
    )
    norm = lambda s: s.replace("-", "")[:8]  # noqa: E731 — index_bars dates are mixed-format
    if start:
        rows = [r for r in rows if norm(r["d"]) >= norm(start)]
    if end:
        rows = [r for r in rows if norm(r["d"]) <= norm(end)]
    closes = [float(r["close"]) for r in rows if r["close"]]
    if len(closes) < 2:
        return [], {"degraded": True, "reason": "hs300_missing_window"}
    daily = [(closes[i] / closes[i - 1] - 1.0) * 100.0 for i in range(1, len(closes))]
    meta = {"degraded": False, "n_days": len(daily),
            "window": {"start": rows[0]["d"], "end": rows[-1]["d"]}}
    return daily, meta
