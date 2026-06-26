"""Industry and size neutralization for cross-sectional factors."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

from quant.features.preprocess import cross_section_z, winsorize


def winsorize_cross_section(values: dict[str, float], *, lower: float = 0.01, upper: float = 0.99) -> dict[str, float]:
    keys = list(values.keys())
    ordered = [values[k] for k in keys]
    clipped = winsorize(ordered, lower=lower, upper=upper)
    return {k: clipped[i] for i, k in enumerate(keys)}


def cross_section_zscores(values: dict[str, float]) -> dict[str, float]:
    return cross_section_z(winsorize_cross_section(values))


def industry_neutral_zscores(
    values: dict[str, float],
    industries: dict[str, str],
    *,
    min_group_size: int = 3,
) -> dict[str, float]:
    """Within-industry demean + rescale to cross-sectional unit variance."""
    by_ind: dict[str, list[str]] = defaultdict(list)
    for sym in values:
        by_ind[industries.get(sym) or "未知"].append(sym)

    demeaned: dict[str, float] = {}
    for ind, syms in by_ind.items():
        vals = [float(values[s]) for s in syms if values.get(s) is not None and values[s] == values[s]]
        if len(vals) < min_group_size:
            mu = statistics.fmean(vals) if vals else 0.0
            for s in syms:
                v = values.get(s)
                demeaned[s] = float(v) - mu if v is not None and v == v else 0.0
            continue
        mu = statistics.fmean(vals)
        for s in syms:
            v = values.get(s)
            demeaned[s] = float(v) - mu if v is not None and v == v else 0.0

    return cross_section_z(demeaned)


def neutralize_size_industry(
    values: dict[str, float],
    *,
    log_market_cap: dict[str, float | None],
    industries: dict[str, str],
) -> dict[str, float]:
    """Residualize factor on log(market_cap) + industry dummies (OLS, numpy-free).

    x_i = a + b*log_cap_i + sum_k gamma_k * 1[industry=k] + epsilon_i
    Returns epsilon_i (size+industry neutral residual), then cross-section z-scored.
    """
    syms = [
        s for s in values
        if values.get(s) is not None and values[s] == values[s]
        and log_market_cap.get(s) is not None and log_market_cap[s] == log_market_cap[s]
    ]
    if len(syms) < 8:
        return industry_neutral_zscores(values, industries)

    inds = sorted({industries.get(s) or "未知" for s in syms})
    ind_index = {ind: i for i, ind in enumerate(inds)}

    # Build normal equations for OLS: (X'X) beta = X'y
    n_feat = 1 + len(inds)  # intercept + industry dummies (drop last for identifiability)
    p = 1 + (len(inds) - 1) + 1  # intercept + (k-1) dummies + log_cap
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p

    for s in syms:
        y = float(values[s])
        cap = float(log_market_cap[s])  # type: ignore[arg-type]
        row = [1.0]
        ind = industries.get(s) or "未知"
        for j, code in enumerate(inds[:-1]):
            row.append(1.0 if ind == code else 0.0)
        row.append(cap)
        for i in range(p):
            xty[i] += row[i] * y
            for j in range(p):
                xtx[i][j] += row[i] * row[j]

    beta = _solve_linear(xtx, xty)
    if beta is None:
        return industry_neutral_zscores(values, industries)

    residuals: dict[str, float] = {}
    for s in syms:
        y = float(values[s])
        cap = float(log_market_cap[s])  # type: ignore[arg-type]
        row = [1.0]
        ind = industries.get(s) or "未知"
        for code in inds[:-1]:
            row.append(1.0 if ind == code else 0.0)
        row.append(cap)
        y_hat = sum(b * row[i] for i, b in enumerate(beta))
        residuals[s] = y - y_hat

    for s in values:
        if s not in residuals:
            residuals[s] = 0.0
    return cross_section_z(residuals)


def _solve_linear(a: list[list[float]], b: list[float]) -> list[float] | None:
    """Gaussian elimination for small systems."""
    n = len(b)
    mat = [a[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = col
        for row in range(col + 1, n):
            if abs(mat[row][col]) > abs(mat[pivot][col]):
                pivot = row
        if abs(mat[pivot][col]) < 1e-12:
            return None
        mat[col], mat[pivot] = mat[pivot], mat[col]
        div = mat[col][col]
        for j in range(col, n + 1):
            mat[col][j] /= div
        for row in range(n):
            if row == col:
                continue
            factor = mat[row][col]
            for j in range(col, n + 1):
                mat[row][j] -= factor * mat[col][j]
    return [mat[i][n] for i in range(n)]


def build_zscore_layers(
    raw_rows: list[dict[str, Any]],
    keys: tuple[str, ...] = ("ret_20", "ret_60", "trend", "vol_20", "avg_amount"),
) -> dict[str, dict[str, dict[str, float]]]:
    """Return {layer: {factor: {symbol: z}}} for market / industry / size_industry."""
    industries = {r["symbol"]: r.get("sector") or "未知" for r in raw_rows}
    log_cap: dict[str, float | None] = {}
    for r in raw_rows:
        mc = r.get("market_cap")
        log_cap[r["symbol"]] = math.log(float(mc)) if mc and float(mc) > 0 else None

    layers: dict[str, dict[str, dict[str, float]]] = {
        "market": {},
        "industry": {},
        "size_industry": {},
    }
    for key in keys:
        vals = {r["symbol"]: float(r[key]) for r in raw_rows if r.get(key) is not None}
        layers["market"][key] = cross_section_zscores(vals)
        layers["industry"][key] = industry_neutral_zscores(vals, industries)
        layers["size_industry"][key] = neutralize_size_industry(vals, log_market_cap=log_cap, industries=industries)
    return layers
