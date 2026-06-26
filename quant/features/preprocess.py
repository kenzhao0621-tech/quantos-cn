"""Cross-section preprocessing: winsorize and robust z-score."""

from __future__ import annotations

import statistics
from typing import Iterable


def winsorize(values: list[float], *, lower: float = 0.01, upper: float = 0.99) -> list[float]:
    """Clip to [lower, upper] quantiles. NaN preserved."""
    clean = [v for v in values if v is not None and v == v]
    if len(clean) < 5:
        return list(values)
    s = sorted(clean)
    lo_i = max(0, int(len(s) * lower))
    hi_i = min(len(s) - 1, int(len(s) * upper))
    lo, hi = s[lo_i], s[hi_i]
    out: list[float] = []
    for v in values:
        if v is None or v != v:
            out.append(float("nan"))
        else:
            out.append(max(lo, min(hi, float(v))))
    return out


def cross_section_z(values: dict[str, float]) -> dict[str, float]:
    """Population z-score on a symbol→value map."""
    keys = [k for k, v in values.items() if v is not None and v == v]
    if len(keys) < 3:
        return {k: 0.0 for k in values}
    vals = [float(values[k]) for k in keys]
    mu = statistics.fmean(vals)
    sd = statistics.pstdev(vals) or 1.0
    return {k: (float(values[k]) - mu) / sd if k in keys and values[k] == values[k] else 0.0 for k in values}


def robust_zscore(values: dict[str, float]) -> dict[str, float]:
    """Median / MAD robust z: (x - median) / (1.4826 * MAD)."""
    keys = [k for k, v in values.items() if v is not None and v == v]
    if len(keys) < 3:
        return {k: 0.0 for k in values}
    vals = sorted(float(values[k]) for k in keys)
    med = vals[len(vals) // 2]
    mad = statistics.median([abs(v - med) for v in vals]) or 1e-9
    scale = 1.4826 * mad
    return {k: (float(values[k]) - med) / scale if k in keys else 0.0 for k in values}
