"""Event-driven backtest wrapper integrating quant PIT checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quant.point_in_time import evaluate_point_in_time_integrity


@dataclass
class BacktestEvent:
    ts: str
    symbol: str
    event_type: str  # BAR | SIGNAL | ORDER | FILL
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    run_id: str
    as_of_date: str
    events: list[BacktestEvent] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    pit_passed: bool = False
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "as_of_date": self.as_of_date,
            "event_count": len(self.events),
            "metrics": self.metrics,
            "pit_passed": self.pit_passed,
            "blockers": self.blockers,
        }


def run_event_backtest(
    *,
    run_id: str,
    as_of_date: str,
    bars: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    snapshot_market_date: str | None = None,
) -> BacktestResult:
    result = BacktestResult(run_id=run_id, as_of_date=as_of_date)
    pit = evaluate_point_in_time_integrity(
        as_of_date=as_of_date,
        snapshot_market_date=snapshot_market_date or as_of_date,
        uses_future_bars=False,
    )
    result.pit_passed = pit.passed
    if not pit.passed:
        result.blockers.append("PIT_FAILED")
        return result

    for bar in bars:
        result.events.append(BacktestEvent(
            ts=str(bar.get("date", as_of_date)),
            symbol=str(bar.get("symbol", "")),
            event_type="BAR",
            payload=bar,
        ))
    for sig in signals:
        result.events.append(BacktestEvent(
            ts=str(sig.get("date", as_of_date)),
            symbol=str(sig.get("symbol", "")),
            event_type="SIGNAL",
            payload=sig,
        ))
        result.events.append(BacktestEvent(
            ts=str(sig.get("date", as_of_date)),
            symbol=str(sig.get("symbol", "")),
            event_type="ORDER",
            payload={"side": sig.get("side", "BUY"), "qty": 100},
        ))
        result.events.append(BacktestEvent(
            ts=str(sig.get("date", as_of_date)),
            symbol=str(sig.get("symbol", "")),
            event_type="FILL",
            payload={"side": sig.get("side", "BUY"), "qty": 100, "price": sig.get("price", 10.0)},
        ))

    fills = [e for e in result.events if e.event_type == "FILL"]
    if fills:
        # Real returns from the provided bar series: fill price → next available
        # close of the same symbol. No resolvable exit → no fabricated metrics.
        closes_by_symbol: dict[str, list[tuple[str, float]]] = {}
        for bar in bars:
            sym = str(bar.get("symbol", ""))
            close = bar.get("close")
            if sym and close:
                closes_by_symbol.setdefault(sym, []).append((str(bar.get("date", "")), float(close)))
        for series in closes_by_symbol.values():
            series.sort()

        rets: list[float] = []
        unresolved = 0
        for fill in fills:
            price = float(fill.payload.get("price") or 0)
            series = closes_by_symbol.get(fill.symbol, [])
            later = [c for d, c in series if d > fill.ts]
            if price > 0 and later:
                rets.append(later[0] / price - 1.0)
            else:
                unresolved += 1

        result.metrics["trades"] = float(len(fills))
        result.metrics["unresolved_fills"] = float(unresolved)
        if rets:
            mean = sum(rets) / len(rets)
            std = (sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)) ** 0.5
            result.metrics["mean_return"] = round(mean, 5)
            result.metrics["sharpe"] = round((mean / std * (252 ** 0.5)), 3) if std > 0 else 0.0
        else:
            result.blockers.append("NO_RESOLVABLE_EXITS — provide bars beyond fill dates for real returns")
    return result
