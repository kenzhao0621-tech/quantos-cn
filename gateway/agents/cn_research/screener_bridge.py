"""TradingAgents-CN style overlay for the screener bottom layer.

Deterministic bull/bear/risk debate + portfolio gate — advisory only, no execution.
Pattern aligned with hsliuping/TradingAgents-CN and gateway/agents/cn_research/prompts.py.
"""

from __future__ import annotations

import uuid
from typing import Any

from gateway.agents.cn_research.prompts import ROLE_PROMPTS


def _bull_points(row: dict[str, Any]) -> list[str]:
    pts: list[str] = []
    if float(row.get("ret_20") or 0) > 0.05:
        pts.append("20日动量偏强")
    if float(row.get("trend") or 0) > 0:
        pts.append("价格站上均线趋势")
    if row.get("live_pct") is not None and float(row["live_pct"]) > 0:
        pts.append(f"实时涨跌幅 {float(row['live_pct']):.2f}%")
    if row.get("dividend_yield") and float(row["dividend_yield"]) > 1:
        pts.append("股息率尚可")
    if not pts:
        pts.append("截面因子综合排名靠前")
    return pts[:4]


def _bear_points(row: dict[str, Any], *, regime_label: str) -> list[str]:
    pts: list[str] = []
    sev = str(row.get("disclosure_flag") or "").upper()
    if sev in {"HIGH", "MEDIUM"}:
        pts.append(f"公告风险 {sev}")
    if float(row.get("vol_20") or 0) > 3:
        pts.append("20日波动偏高")
    lp = row.get("live_pct")
    if lp is not None and float(lp) >= 9.0:
        pts.append("接近涨停，追高空间有限")
    if float(row.get("last_pct") or 0) >= 9.5:
        pts.append("昨收涨停附近，T+1 接力风险")
    if regime_label.lower() in {"risk_off", "bear", "weak"}:
        pts.append("市场 regime 偏弱，多头置信度下调")
    pts.append("T+1 与涨跌停约束")
    return pts[:5]


def _agent_score_delta(row: dict[str, Any], *, regime_label: str) -> float:
    """Small score nudge from agent debate (-0.8 .. +0.8)."""
    delta = 0.0
    delta += min(0.35, float(row.get("ret_20") or 0) * 2)
    delta += min(0.2, float(row.get("trend") or 0) * 1.5)
    if row.get("live_pct") is not None:
        delta += max(-0.4, min(0.25, float(row["live_pct"]) / 20))
    sev = str(row.get("disclosure_flag") or "").upper()
    if sev == "HIGH":
        delta -= 0.7
    elif sev == "MEDIUM":
        delta -= 0.35
    if float(row.get("vol_20") or 0) > 4:
        delta -= 0.2
    if regime_label.lower() in {"risk_off", "bear", "weak"}:
        delta -= 0.25
    trad_blockers = row.get("tradability_blockers") or []
    if trad_blockers:
        delta -= 0.5
    return max(-0.8, min(0.8, delta))


def apply_trading_agents_zh_overlay(
    ranked_rows: list[dict[str, Any]],
    *,
    as_of_date: str | None,
    mode: str,
    live_status: dict[str, Any],
    regime: dict[str, Any] | None = None,
    capital_cny: float = 5000.0,
    fast: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run TradingAgents-CN panel on top candidates; optionally re-rank."""
    regime_label = str((regime or {}).get("label") or "UNKNOWN")
    blockers: list[str] = []
    if not live_status.get("used") and str(mode).lower() in ("live", "realtime", "intraday"):
        blockers.append("LIVE_QUOTES_NOT_USED")
    if live_status.get("blocked"):
        blockers.append(str(live_status.get("reason") or "LIVE_BLOCKED"))

    overlays: dict[str, dict[str, Any]] = {}
    for row in ranked_rows:
        sym = row["symbol"]
        bull = _bull_points(row)
        bear = _bear_points(row, regime_label=regime_label)
        risk_verdict = "REJECT" if blockers or bear[0].startswith("公告风险 HIGH") else (
            "PASS_WITH_CAUTION" if len(bear) > 3 else "PASS"
        )
        adj = _agent_score_delta(row, regime_label=regime_label)
        overlays[sym] = {
            "bull_points": bull,
            "bear_points": bear,
            "risk_verdict": risk_verdict,
            "agent_score_delta": round(adj, 4),
            "roles": {
                "BullResearcherCN": bull[0] if bull else "",
                "BearResearcherCN": bear[0] if bear else "",
                "RiskOfficerCN": risk_verdict,
            },
        }
        if not fast and adj:
            row["score"] = float(row.get("score") or 0) + adj
            row["agent_score_delta"] = adj

    if not fast:
        ranked_rows.sort(key=lambda r: float(r.get("score") or 0), reverse=True)
        for i, row in enumerate(ranked_rows):
            row["rank"] = i + 1

    sample_syms = [r["symbol"] for r in ranked_rows[:5]]
    bull_summary = "；".join(
        f"{r['symbol']}:{overlays[r['symbol']]['bull_points'][0]}"
        for r in ranked_rows[:3]
        if r["symbol"] in overlays and overlays[r["symbol"]]["bull_points"]
    )
    bear_summary = "；".join(
        overlays[s]["bear_points"][0] for s in sample_syms if s in overlays
    ) or "T+1/涨跌停/数据新鲜度"

    portfolio_verdict = "NO_TRADE" if blockers else (
        "TRADE_CANDIDATE" if len(ranked_rows) >= 3 else "INSUFFICIENT_SAMPLE"
    )
    panel = {
        "framework": "TradingAgents-CN",
        "pattern": "bull_bear_risk_gate",
        "role_prompts_version": len(ROLE_PROMPTS),
        "bull_summary": bull_summary or "多头：截面因子领先",
        "bear_summary": bear_summary,
        "risk_verdict": "REJECT" if blockers else "PASS_WITH_CAUTION",
        "portfolio_verdict": portfolio_verdict,
        "candidate_gate": "BLOCKED_BY_DATA" if blockers else "CANDIDATE_DATA_READY",
        "execution_allowed": False,
        "capital_cny": capital_cny,
        "mode": mode,
        "as_of_date": as_of_date,
        "sample_symbols": sample_syms,
        "blockers": blockers,
    }
    meta = {
        "run_id": str(uuid.uuid4())[:12],
        "panel": panel,
        "overlays": overlays,
        "candidate_count": len(ranked_rows),
    }
    return ranked_rows, meta
