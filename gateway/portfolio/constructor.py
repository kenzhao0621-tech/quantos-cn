"""Portfolio constructor with risk-aware sizing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Candidate:
    symbol: str
    score: float
    confidence: float
    entry_zone: str
    stop: str
    target1: str
    research_only: bool = True


@dataclass
class PortfolioProposal:
    run_id: str
    as_of_date: str
    candidates: list[Candidate] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    cash_buffer_pct: float = 0.5
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "as_of_date": self.as_of_date,
            "candidates": [
                {
                    "symbol": c.symbol,
                    "score": c.score,
                    "confidence": c.confidence,
                    "entry_zone": c.entry_zone,
                    "stop": c.stop,
                    "target1": c.target1,
                    "research_only": c.research_only,
                }
                for c in self.candidates
            ],
            "weights": self.weights,
            "cash_buffer_pct": self.cash_buffer_pct,
            "blockers": self.blockers,
        }


def construct_portfolio(
    *,
    run_id: str,
    as_of_date: str,
    ranked_symbols: list[tuple[str, float]],
    max_positions: int = 2,
    max_single_weight: float = 0.25,
    min_cash_buffer_pct: float = 0.5,
) -> PortfolioProposal:
    proposal = PortfolioProposal(run_id=run_id, as_of_date=as_of_date, cash_buffer_pct=min_cash_buffer_pct)
    if not ranked_symbols:
        proposal.blockers.append("NO_CANDIDATES")
        return proposal
    selected = ranked_symbols[:max_positions]
    investable = 1.0 - min_cash_buffer_pct
    per = min(investable / len(selected), max_single_weight)
    for sym, score in selected:
        proposal.candidates.append(Candidate(
            symbol=sym, score=score, confidence=min(1.0, score / 100.0),
            entry_zone="limit_band", stop="-5%", target1="+8%", research_only=True,
        ))
        proposal.weights[sym] = round(per, 4)
    return proposal
