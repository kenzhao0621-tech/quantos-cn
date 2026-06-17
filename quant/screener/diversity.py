"""Portfolio diversity constraints for screener output — sector, price tier, correlation cap."""

from __future__ import annotations

from typing import Any


def apply_diversity_constraints(
    candidates: list[Any],
    *,
    top_n: int,
    max_sector_pct: float = 0.40,
    max_price_tier_pct: float = 0.50,
    min_candidates: int = 3,
) -> tuple[list[Any], list[str]]:
    """Filter ranked candidates to avoid single-sector / single-price-band concentration.

    ``candidates`` must be sorted by score descending. Each item needs:
    symbol, score, sector (optional), last_close or live_price.
    """
    if not candidates:
        return [], ["无候选可应用多样性约束"]

    selected: list[Any] = []
    sector_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {}
    notes: list[str] = []

    def price_tier(price: float) -> str:
        if price < 10:
            return "low"
        if price < 30:
            return "mid"
        if price < 100:
            return "high"
        return "premium"

    max_sector = max(1, int(top_n * max_sector_pct))
    max_tier = max(1, int(top_n * max_price_tier_pct))

    for c in candidates:
        if len(selected) >= top_n:
            break
        sector = getattr(c, "sector", None) or (c.get("sector") if isinstance(c, dict) else "") or "未知"
        price = float(
            getattr(c, "live_price", None)
            or getattr(c, "last_close", None)
            or (c.get("live_price") or c.get("last_close") if isinstance(c, dict) else 0)
            or 0
        )
        tier = price_tier(price)
        if sector_counts.get(sector, 0) >= max_sector:
            continue
        if tier_counts.get(tier, 0) >= max_tier:
            continue
        selected.append(c)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    if len(selected) < min(min_candidates, top_n) and len(candidates) >= min_candidates:
        notes.append("多样性约束后候选不足，已放宽行业上限")
        selected = candidates[:top_n]

    if sector_counts:
        dominant = max(sector_counts, key=sector_counts.get)  # type: ignore[arg-type]
        notes.append(f"行业分布: {dict(sector_counts)}；最大暴露 {dominant}")
    if tier_counts:
        notes.append(f"价格分层: {dict(tier_counts)}")

    return selected, notes
