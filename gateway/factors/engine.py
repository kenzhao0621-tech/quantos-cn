"""Factor engine — lightweight factor computation over warehouse features."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FactorRow:
    symbol: str
    as_of_date: str
    factors: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "as_of_date": self.as_of_date, "factors": self.factors}


def compute_momentum_factor(closes: list[float], window: int = 20) -> float | None:
    if len(closes) < window + 1:
        return None
    return (closes[-1] / closes[-window - 1]) - 1.0


def compute_volatility_factor(returns: list[float], window: int = 20) -> float | None:
    if len(returns) < window:
        return None
    sample = returns[-window:]
    mean = sum(sample) / len(sample)
    var = sum((r - mean) ** 2 for r in sample) / max(1, len(sample) - 1)
    return var ** 0.5


def rank_factors(rows: list[FactorRow], factor_name: str) -> list[FactorRow]:
    scored = [(r, r.factors.get(factor_name)) for r in rows]
    scored = [(r, v) for r, v in scored if v is not None]
    scored.sort(key=lambda x: x[1], reverse=True)
    for i, (row, val) in enumerate(scored):
        row.factors[f"{factor_name}_rank"] = float(i + 1)
        row.factors[f"{factor_name}_score"] = val
    return [r for r, _ in scored]
