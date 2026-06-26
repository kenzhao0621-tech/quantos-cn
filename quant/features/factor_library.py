"""Expanded factor library — orthogonal clusters beyond price momentum."""

from __future__ import annotations

import math
import statistics
from typing import Any


FACTOR_VERSION = "factor_library_v2_2026-06-17"


def compute_price_factors(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    amounts: list[float] | None = None,
    pct_chgs: list[float] | None = None,
) -> dict[str, float | None]:
    """Compute raw factor values from trailing bar series (oldest→newest)."""
    if len(closes) < 21:
        return {}
    c = [float(x) for x in closes]
    n = len(c)
    rets = pct_chgs or []
    if not rets and n > 1:
        rets = [(c[i] / c[i - 1] - 1) if c[i - 1] else 0.0 for i in range(1, n)]
        rets = [0.0] + rets

    def ret(k: int) -> float | None:
        return c[-1] / c[-k - 1] - 1 if n > k else None

    ma = lambda w: statistics.fmean(c[-w:]) if n >= w else None
    ma20, ma60 = ma(20), ma(60)
    vol20 = statistics.pstdev(rets[-20:]) * 100 if len(rets) >= 20 else None
    vol60 = statistics.pstdev(rets[-60:]) * 100 if len(rets) >= 60 else None
    down = [min(0.0, r) for r in rets[-20:]] if len(rets) >= 20 else []
    downside_vol = statistics.pstdev(down) * 100 if len(down) >= 5 else None

    peak = max(c[-60:]) if n >= 60 else max(c)
    max_dd = c[-1] / peak - 1 if peak else None

    h = highs or c
    l = lows or c
    hi60 = max(h[-60:]) if n >= 60 else max(h)
    lo60 = min(l[-60:]) if n >= 60 else min(l)
    price_pos = (c[-1] - lo60) / (hi60 - lo60) if hi60 > lo60 else None

    amt = amounts or []
    avg_amt20 = statistics.fmean(amt[-20:]) if len(amt) >= 20 else None
    amihud = None
    if amt and len(amt) >= 20 and len(rets) >= 20:
        ratios = [abs(rets[-20 + i]) / max(amt[-20 + i], 1.0) for i in range(20)]
        amihud = statistics.fmean(ratios)

    rev_1 = -rets[-1] if rets else None
    rev_5 = -(ret(5) or 0) if ret(5) is not None else None

    vol_spike = None
    if amt and len(amt) >= 20:
        m = statistics.fmean(amt[-20:])
        vol_spike = amt[-1] / m - 1 if m else None

    return {
        "ret_5": ret(5),
        "ret_20": ret(20),
        "ret_60": ret(60) if n > 60 else None,
        "ret_120": ret(120) if n > 120 else None,
        "mom_20_5": (c[-6] / c[-21] - 1) if n > 21 else None,
        "mom_60_20": (c[-21] / c[-61] - 1) if n > 61 else None,
        "rev_1": rev_1,
        "rev_5": rev_5,
        "trend_20": c[-1] / ma20 - 1 if ma20 else None,
        "trend_60": c[-1] / ma60 - 1 if ma60 else None,
        "ma_cross": ma20 / ma60 - 1 if ma20 and ma60 else None,
        "price_position_60": price_pos,
        "vol_20": vol20,
        "vol_60": vol60,
        "downside_vol_20": downside_vol,
        "max_drawdown_60": max_dd,
        "amihud_20": amihud,
        "avg_amount_20": avg_amt20,
        "volume_spike": vol_spike,
    }


def compute_fundamental_factors(fund: dict[str, Any]) -> dict[str, float | None]:
    """Value / quality / growth from fundamentals row. NaN if invalid — never fake."""
    out: dict[str, float | None] = {}
    pe = _f(fund.get("pe") or fund.get("pe_ttm"))
    pb = _f(fund.get("pb"))
    ps = _f(fund.get("ps_ttm"))
    dv = _f(fund.get("dv_ttm"))
    out["value_pe"] = -math.log(pe) if pe and pe > 0 else None
    out["value_pb"] = -math.log(pb) if pb and pb > 0 else None
    out["value_ps"] = -math.log(ps) if ps and ps > 0 else None
    out["dividend_yield"] = dv
    for k in ("roe", "roa", "gross_margin", "net_margin", "debt_to_asset", "revenue_yoy", "profit_yoy"):
        v = _f(fund.get(k))
        out[k] = v
    out["quality_debt"] = -out["debt_to_asset"] if out.get("debt_to_asset") is not None else None
    return out


def composite_value_quality_growth(factors: dict[str, float | None]) -> dict[str, float | None]:
    """Simple composites for industry-relative factors."""
    vals = [factors.get("value_pe"), factors.get("value_pb"), factors.get("value_ps")]
    clean = [v for v in vals if v is not None and v == v]
    value_score = statistics.fmean(clean) if clean else None
    q = [factors.get("roe"), factors.get("roa"), factors.get("gross_margin")]
    qc = [v for v in q if v is not None and v == v]
    quality_score = statistics.fmean(qc) if qc else None
    g = [factors.get("revenue_yoy"), factors.get("profit_yoy")]
    gc = [v for v in g if v is not None and v == v]
    growth_score = statistics.fmean(gc) if gc else None
    return {"value_score": value_score, "quality_score": quality_score, "growth_score": growth_score}


def industry_relative(factors: dict[str, float | None], peer_factors: list[dict[str, float | None]], key: str) -> float | None:
    v = factors.get(key)
    if v is None or v != v:
        return None
    peers = [p.get(key) for p in peer_factors if p.get(key) is not None and p[key] == p[key]]
    if len(peers) < 2:
        return 0.0
    return float(v) - statistics.fmean(peers)


def risk_event_score(severity: str) -> float:
    s = (severity or "").upper()
    if s == "HIGH":
        return -2.0
    if s == "MEDIUM":
        return -1.0
    if s == "LOW":
        return -0.3
    return 0.0


def _f(val: Any) -> float | None:
    try:
        if val is None:
            return None
        x = float(val)
        return None if x != x else x
    except (TypeError, ValueError):
        return None
