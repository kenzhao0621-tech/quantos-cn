"""Cross-source reconciliation for live datasets."""

from __future__ import annotations

from typing import Any

from quant.provider_result import ProviderResult


def _norm_code(code: str) -> str:
    c = str(code).lower().strip()
    for p in ("sh", "sz", "bj"):
        if c.startswith(p):
            c = c[len(p):]
    return c.zfill(6)


def _price_map(result: ProviderResult) -> dict[str, float]:
    payload = result.payload
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("rows", [])
    out: dict[str, float] = {}
    for r in rows:
        code = _norm_code(r.get("code", ""))
        price = float(r.get("price") or 0)
        if code and price > 0:
            out[code] = price
    return out


def reconcile_live_sources(
    dataset: str,
    results: list[ProviderResult],
    config: dict[str, Any],
) -> dict[str, Any]:
    if len(results) < 2:
        return {"dataset": dataset, "compared": 0, "quarantine": False}

    price_tol = config.get("price_relative_difference_max", 0.005)
    overlap_min = config.get("symbol_overlap_min", 0.98)
    a, b = results[0], results[1]
    pa, pb = _price_map(a), _price_map(b)
    common = set(pa) & set(pb)
    overlap = len(common) / max(len(pa), len(pb), 1)
    mismatches: list[dict[str, Any]] = []
    for code in list(common)[:500]:
        p1, p2 = pa[code], pb[code]
        if p1 <= 0:
            continue
        rel = abs(p1 - p2) / p1
        if rel > price_tol:
            mismatches.append({"code": code, "a": p1, "b": p2, "rel_diff": rel})

    date_match = True
    if config.get("market_date_must_match", True):
        date_match = (a.market_date or "") == (b.market_date or "") or not a.market_date

    quarantine = overlap < overlap_min or len(mismatches) > 0 or not date_match
    return {
        "dataset": dataset,
        "providers": [a.provider, b.provider],
        "symbol_overlap": round(overlap, 4),
        "mismatch_count": len(mismatches),
        "sample_mismatches": mismatches[:5],
        "market_date_match": date_match,
        "quarantine": quarantine,
        "action": "QUARANTINE_DATASET" if quarantine else "PASS",
    }
