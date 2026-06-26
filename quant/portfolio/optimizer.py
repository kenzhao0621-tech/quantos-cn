"""Portfolio construction with industry and single-name constraints."""

from __future__ import annotations

from typing import Any

from quant.portfolio.constraints import DEFAULT_CONSTRAINTS


def optimize_topk(
    candidates: list[dict[str, Any]],
    *,
    top_k: int = 20,
    max_single_weight: float | None = None,
    max_industry_weight: float | None = None,
    regime_position_scale: tuple[float, float] = (0.5, 0.8),
) -> dict[str, Any]:
    """Greedy weight assignment under constraints — not full QP but real constraints."""
    c = DEFAULT_CONSTRAINTS
    max_single_weight = max_single_weight if max_single_weight is not None else c.max_single_weight
    max_industry_weight = max_industry_weight if max_industry_weight is not None else c.max_industry_weight
    if not candidates:
        return {"weights": {}, "positions": [], "total_weight": 0.0, "notes": ["empty universe"]}

    sorted_c = sorted(candidates, key=lambda r: float(r.get("score") or 0), reverse=True)
    cap_min, cap_max = regime_position_scale
    gross = (cap_min + cap_max) / 2.0

    weights: dict[str, float] = {}
    industry_totals: dict[str, float] = {}
    notes: list[str] = []
    per = min(max_single_weight, gross / max(1, top_k))

    for row in sorted_c[: top_k * 3]:
        sym = row["symbol"]
        if sym in weights:
            continue
        sector = row.get("sector") or "未知"
        ind_w = industry_totals.get(sector, 0.0)
        if ind_w + per > max_industry_weight:
            notes.append(f"skip {sym}: industry {sector} cap")
            continue
        if sum(weights.values()) + per > gross:
            break
        weights[sym] = round(per, 4)
        industry_totals[sector] = ind_w + per
        if len(weights) >= top_k:
            break

    # Renormalize to target gross without breaching single-name cap
    total = sum(weights.values())
    if total > 1e-9:
        scale = min(gross / total, 1.0)
        weights = {k: round(min(v * scale, max_single_weight), 4) for k, v in weights.items()}

    positions = [
        {
            "symbol": s,
            "weight": w,
            "name": next((c.get("name") for c in sorted_c if c["symbol"] == s), ""),
            "sector": next((c.get("sector") for c in sorted_c if c["symbol"] == s), ""),
        }
        for s, w in sorted(weights.items(), key=lambda x: -x[1])
    ]
    return {
        "weights": weights,
        "positions": positions,
        "total_weight": round(sum(weights.values()), 4),
        "constraints": {
            "max_single_weight": max_single_weight,
            "max_industry_weight": max_industry_weight,
            "regime_gross": regime_position_scale,
        },
        "notes": notes[:10],
    }
