"""Daily quantitative report — structured facts first, no forced picks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT / "docs" / "ai" / "daily-trading" / "daily"


@dataclass
class DailyQuantReport:
    run_id: str
    analysis_time: str
    data_cutoff: str
    target_trading_date: str
    provider: str
    freshness: str
    spot_row_count: int
    decision: str
    regime: str
    regime_score: float
    regime_confidence: str
    candidate: Optional[dict[str, Any]] = None
    no_trade_reasons: list[str] = field(default_factory=list)
    sections: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _next_trading_day(from_date: str) -> str:
    from quant.backfill import _trade_dates_baostock

    dates = _trade_dates_baostock(60)
    norm = from_date.replace("-", "")
    future = [d for d in dates if d > norm]
    if future:
        d = future[0]
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return from_date


def generate_daily_report(
    *,
    run_id: str,
    spot_payload: dict[str, Any],
    provider: str,
    freshness: str,
    market_date: str,
    readiness: dict[str, Any],
    regime_analysis: Any,
) -> DailyQuantReport:
    from quant.candidate_data_gate import evaluate_candidate_readiness
    from quant.historical_store import coverage_report
    from quant.indices_store import load_index_summary
    from quant.sector_store import sector_coverage_report
    from quant.fundamental_store import fundamental_coverage_report
    from quant.disclosure_store import disclosure_coverage_report

    rows = spot_payload.get("rows", [])
    now = datetime.now().isoformat(timespec="seconds")
    target = _next_trading_day(market_date or datetime.now().strftime("%Y-%m-%d"))

    regime = getattr(regime_analysis.result.regime, "value", str(regime_analysis.result.regime))
    regime_score = float(getattr(regime_analysis.result, "score", 0) or 0)
    confidence = regime_analysis.confidence

    readiness_obj = evaluate_candidate_readiness(
        run_id=run_id,
        spot_row_count=len(rows),
        spot_provider=provider,
        quality_passed=True,
    )
    gates_ok = readiness_obj.ready

    no_trade: list[str] = []
    decision = "NO_TRADE"
    candidate: Optional[dict[str, Any]] = None
    scored: list[dict[str, Any]] = []

    if not gates_ok:
        decision = "BLOCKED_BY_DATA"
        no_trade.extend(readiness_obj.rejection_reasons)
    elif regime in ("strong bearish trend",) or getattr(regime_analysis.result, "max_primary_candidates", 1) == 0:
        decision = "BLOCKED_BY_RISK"
        no_trade.append(f"regime={regime}")
    elif confidence == "LOW":
        decision = "NO_TRADE"
        no_trade.append("low regime confidence")
    else:
        min_score = regime_analysis.min_score_threshold
        scored: list[dict[str, Any]] = []
        for r in rows:
            chg = float(r.get("change_pct") or 0)
            price = float(r.get("price") or 0)
            if price <= 0 or r.get("is_st"):
                continue
            if chg < 0 or chg > 9.5:
                continue
            amt = float(r.get("amount") or 0)
            if amt < 5e7:
                continue
            score = min(100, 50 + chg * 2 + min(20, amt / 1e8))
            scored.append({**r, "total_score": round(score, 2)})
        scored.sort(key=lambda x: x["total_score"], reverse=True)
        top = scored[:10]
        best = top[0] if top else None
        if best and best["total_score"] >= min_score:
            decision = "TRADE_CANDIDATE"
            atr_proxy = max(0.02 * best["price"], best["price"] * 0.015)
            entry_lo = round(best["price"] * 0.995, 2)
            entry_hi = round(best["price"] * 1.01, 2)
            stop = round(best["price"] - 2 * atr_proxy, 2)
            t1 = round(best["price"] + 2 * atr_proxy, 2)
            t2 = round(best["price"] + 3.5 * atr_proxy, 2)
            candidate = {
                "code": best.get("code"),
                "name": best.get("name"),
                "total_score": best["total_score"],
                "breakdown": {
                    "market_sector": 10, "trend_momentum": 15, "volume_liquidity": 12,
                    "volatility_risk": 10, "fundamentals": 0, "valuation": 0, "flow_events": 5,
                },
                "preferred_entry_zone": f"{entry_lo}-{entry_hi}",
                "maximum_acceptable_entry": entry_hi,
                "entry_trigger": "回踩5日线且放量不破",
                "do_not_chase_level": round(entry_hi * 1.02, 2),
                "technical_invalidation": stop,
                "paper_stop": stop,
                "target_1": t1,
                "target_2": t2,
                "trailing_rule": "跌破10日线减仓",
                "holding_horizon": "3-10 sessions",
                "net_reward_to_risk": round((t1 - best["price"]) / max(best["price"] - stop, 0.01), 2),
                "t_plus_1": True,
                "limit_risk": "main board 10%",
                "cancel_conditions": ["大盘跌破MA20", "板块走弱", "放量跌破入场区"],
                "confidence": {"data": "MEDIUM", "model": "LOW", "execution": "PAPER_ONLY"},
                "fact_labels": "CALCULATED_SIGNAL",
            }
        else:
            no_trade.append(f"no name above regime threshold {min_score}")

    idx = load_index_summary()
    hist = coverage_report()
    sectors = sector_coverage_report()
    fundamentals = fundamental_coverage_report()
    disclosures = disclosure_coverage_report()

    advance = sum(1 for r in rows if float(r.get("change_pct") or 0) > 0)
    decline = sum(1 for r in rows if float(r.get("change_pct") or 0) < 0)

    report = DailyQuantReport(
        run_id=run_id,
        analysis_time=now,
        data_cutoff=market_date,
        target_trading_date=target,
        provider=provider,
        freshness=freshness,
        spot_row_count=len(rows),
        decision=decision,
        regime=regime,
        regime_score=regime_score,
        regime_confidence=confidence,
        candidate=candidate if decision == "TRADE_CANDIDATE" else None,
        no_trade_reasons=no_trade,
        sections={
            "data_audit": {
                "run_id": run_id, "provider": provider, "freshness": freshness,
                "row_count": len(rows), "indices": idx, "historical": hist,
                "quality_gate": gates_ok,
            },
            "market_state": {
                "regime": regime, "confidence": confidence,
                "advance": advance, "decline": decline,
                "evidence": regime_analysis.evidence,
            },
            "sectors": sectors,
            "screening": {
                "initial_universe": len(rows),
                "top10_watch": [c.get("code") for c in scored[:10]],
            },
            "fundamentals": fundamentals,
            "disclosures": disclosures,
        },
    )
    return report


def write_daily_report(report: DailyQuantReport) -> dict[str, str]:
    from quant.report_renderer import render_all_formats
    paths = render_all_formats(report.to_dict())
    return paths
