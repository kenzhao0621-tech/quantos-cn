"""Shared data models for China quant pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from tools.china_quant.data import MarketSnapshot


@dataclass
class SectorInfo:
    name: str
    strength_score: float
    momentum_pct: float
    breadth_pct: float
    phase: str  # early | mature | overheated
    thesis: str
    invalidation: str
    catalyst_status: str  # confirmed | speculative


@dataclass
class StockRecord:
    code: str
    name: str
    exchange: str
    board: str
    sector: str
    price: float
    change_pct: float
    avg_daily_value_m: float
    is_st: bool = False
    suspended: bool = False
    at_limit_up: bool = False
    at_limit_down: bool = False
    newly_listed_days: int = 999
    rumor_only_catalyst: bool = False
    official_catalyst: str = ""
    trend_score: float = 0.0
    fundamental_score: float = 0.0
    valuation_score: float = 0.0


@dataclass
class MarketBundle:
    snapshot: MarketSnapshot
    sectors: list[SectorInfo] = field(default_factory=list)
    stocks: list[StockRecord] = field(default_factory=list)
    fixture_label: str = ""
    assumptions: list[str] = field(default_factory=list)


def bundle_from_fixture(data: dict[str, Any]) -> MarketBundle:
    from tools.china_quant.data import snapshot_from_fixture

    snap = snapshot_from_fixture(data)
    sectors = [
        SectorInfo(
            name=s["name"],
            strength_score=float(s["strength_score"]),
            momentum_pct=float(s["momentum_pct"]),
            breadth_pct=float(s.get("breadth_pct", 50)),
            phase=s.get("phase", "mature"),
            thesis=s.get("thesis", ""),
            invalidation=s.get("invalidation", ""),
            catalyst_status=s.get("catalyst_status", "speculative"),
        )
        for s in data.get("sectors", [])
    ]
    stocks = [
        StockRecord(
            code=st["code"],
            name=st["name"],
            exchange=st.get("exchange", "SH"),
            board=st.get("board", "MAIN_SH"),
            sector=st["sector"],
            price=float(st["price"]),
            change_pct=float(st.get("change_pct", 0)),
            avg_daily_value_m=float(st.get("avg_daily_value_m", 100)),
            is_st=st.get("is_st", False),
            suspended=st.get("suspended", False),
            at_limit_up=st.get("at_limit_up", False),
            at_limit_down=st.get("at_limit_down", False),
            newly_listed_days=int(st.get("newly_listed_days", 999)),
            rumor_only_catalyst=st.get("rumor_only_catalyst", False),
            official_catalyst=st.get("official_catalyst", ""),
            trend_score=float(st.get("trend_score", 0)),
            fundamental_score=float(st.get("fundamental_score", 0)),
            valuation_score=float(st.get("valuation_score", 0)),
        )
        for st in data.get("stocks", [])
    ]
    return MarketBundle(
        snapshot=snap,
        sectors=sectors,
        stocks=stocks,
        fixture_label=data.get("fixture_label", ""),
        assumptions=data.get("assumptions", []),
    )
