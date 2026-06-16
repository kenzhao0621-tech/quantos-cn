"""Alpha158-lite feature dataset from warehouse bars."""

from __future__ import annotations

from typing import Any

from integrations.qlib.provider import CNMarketProvider


def build_alpha158_lite(*, as_of: str, symbols: list[str] | None = None) -> dict[str, Any]:
    """Deterministic baseline features without requiring native Qlib."""
    provider = CNMarketProvider()
    bars = provider.load_daily_bars(limit=5000)
    bars = provider.pit_filter(bars, as_of)
    if symbols:
        sym_set = set(symbols)
        bars = [b for b in bars if b.get("ts_code") in sym_set or b.get("code") in sym_set]

    features: list[dict[str, Any]] = []
    by_sym: dict[str, list[dict]] = {}
    for b in bars:
        sym = b.get("ts_code") or b.get("code") or ""
        by_sym.setdefault(sym, []).append(b)

    for sym, series in by_sym.items():
        if len(series) < 5:
            continue
        closes = [float(x.get("close") or x.get("close_price") or 0) for x in series[-20:]]
        if not closes or closes[-1] <= 0:
            continue
        mom = (closes[-1] / closes[0] - 1) if closes[0] else 0
        vol = (max(closes) - min(closes)) / closes[-1] if closes[-1] else 0
        features.append({
            "symbol": sym,
            "as_of": as_of,
            "MOM20": round(mom, 6),
            "VOL20": round(vol, 6),
            "RET1": round((closes[-1] / closes[-2] - 1) if len(closes) > 1 else 0, 6),
            "LIQ_PROXY": round(float(series[-1].get("amount") or series[-1].get("volume") or 0), 2),
        })

    return {
        "dataset": "alpha158_lite",
        "as_of": as_of,
        "row_count": len(features),
        "features": features[:500],
        "pit_filtered": True,
    }
