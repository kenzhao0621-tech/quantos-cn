"""Forward return labels with T+1 execution semantics (A-share)."""

from __future__ import annotations

from typing import Any


def label_close_to_close(
    close_by_date: dict[str, float],
    dates: list[str],
    signal_idx: int,
    horizon: int,
) -> float | None:
    """label_tk_cc = close[t+k] / close[t+1] - 1 (signal at T close, buy T+1)."""
    if signal_idx + horizon + 1 >= len(dates):
        return None
    d0 = dates[signal_idx + 1]
    dk = dates[signal_idx + horizon + 1]
    c0, ck = close_by_date.get(d0), close_by_date.get(dk)
    if not c0 or not ck or c0 <= 0:
        return None
    return ck / c0 - 1.0


def build_labels_for_symbol(
    bars: list[tuple[str, float]],
    *,
    industry_returns: dict[str, float] | None = None,
    market_return: float | None = None,
) -> list[dict[str, Any]]:
    """bars: [(trade_date, close), ...] sorted ascending."""
    dates = [d for d, _ in bars]
    close = {d: c for d, c in bars}
    rows: list[dict[str, Any]] = []
    for i, d in enumerate(dates):
        if i + 21 >= len(dates):
            break
        t1 = label_close_to_close(close, dates, i, 1)
        t5 = label_close_to_close(close, dates, i, 5)
        t20 = label_close_to_close(close, dates, i, 20)
        excess_mkt = (t5 - market_return) if t5 is not None and market_return is not None else None
        excess_ind = (t5 - industry_returns.get(d)) if t5 is not None and industry_returns and d in industry_returns else None
        rows.append({
            "trade_date": d,
            "label_t1_cc": round(t1, 6) if t1 is not None else None,
            "label_t5_cc": round(t5, 6) if t5 is not None else None,
            "label_t20_cc": round(t20, 6) if t20 is not None else None,
            "label_t5_excess_market": round(excess_mkt, 6) if excess_mkt is not None else None,
            "label_t5_excess_industry": round(excess_ind, 6) if excess_ind is not None else None,
            "tradable_at_t_plus_1": True,
        })
    return rows


def rank_label_buckets(labels: list[float], n_buckets: int = 5) -> list[int]:
    """Cross-section rank labels 0..n_buckets-1 for LambdaRank-style training."""
    if not labels:
        return []
    order = sorted(range(len(labels)), key=lambda i: labels[i])
    out = [0] * len(labels)
    per = max(1, len(labels) // n_buckets)
    for rank, idx in enumerate(order):
        out[idx] = min(n_buckets - 1, rank // per)
    return out
