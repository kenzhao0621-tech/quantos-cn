"""AgentsOS pipeline — orchestrate 9 agents, debate, veto, final A/B/C/D/BLOCKED."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from gateway.agents.quantos.roles import (
    bear_researcher,
    bull_researcher,
    fundamental_agent,
    market_regime_agent,
    portfolio_manager,
    risk_manager,
    sentiment_agent,
    technical_agent,
)

ROOT = Path(__file__).resolve().parents[3]

RATING_LEGEND = {
    "A": "高置信研究候选，不代表一定盈利",
    "B": "可观察候选",
    "C": "中性/不建议行动",
    "D": "风险过高",
    "BLOCKED": "数据不足、风控不通过、回测不通过或不可交易",
}


def final_advisor(ctx: dict[str, Any], upstream: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rm = upstream.get("RiskManager") or {}
    pm = upstream.get("PortfolioManager") or {}
    bull = upstream.get("BullResearcher") or {}
    bear = upstream.get("BearResearcher") or {}

    degraded_agents = [n for n, a in upstream.items() if a.get("degraded")]
    composite = sum(upstream.get(n, {}).get("score", 0) for n in
                    ("TechnicalAgent", "FundamentalAgent", "SentimentAgent", "MarketRegimeAgent")) / 4
    mean_conf = sum(a.get("confidence", 0) for a in upstream.values()) / max(len(upstream), 1)

    if rm.get("must_not_trade") or pm.get("must_not_trade"):
        grade = "BLOCKED"
    elif composite >= 0.30 and mean_conf >= 0.5 and not rm.get("risks"):
        grade = "A"
    elif composite >= 0.12:
        grade = "B"
    elif composite <= -0.20 or len(rm.get("risks") or []) >= 3:
        grade = "D"
    else:
        grade = "C"

    invalidation = [
        "跌破 MA20 且 20 日动量转负",
        "出现停牌/ST/退市风险等硬性风险标记",
        "大盘状态转为 BEAR_TREND",
        "最新回测/验证门变为 BLOCKED_BY_VALIDATION",
    ]
    return {
        "agent": "FinalAdvisor",
        "rating": grade,
        "rating_meaning": RATING_LEGEND[grade],
        "score": round(composite, 3),
        "confidence": round(mean_conf, 3),
        "bull_case": bull.get("key_points", []),
        "bear_case": bear.get("key_points", []),
        "risks": rm.get("risks", []),
        "position_advice": pm.get("key_points", []),
        "invalidation_conditions": invalidation,
        "evidence_refs": sorted({r for a in upstream.values() for r in a.get("evidence_refs", [])}),
        "degraded_agents": degraded_agents,
        "must_not_trade": grade == "BLOCKED",
        "degraded": bool(degraded_agents),
        "disclaimer": "本结论为研究性输出，经过验证不代表未来盈利；仅供研究与辅助决策，不构成投资建议。",
    }


def run_agents_analysis(symbol: str, *, as_of_date: str | None = None,
                        persist: bool = True) -> dict[str, Any]:
    from gateway.agents.quantos.inputs import build_agent_input

    ctx = build_agent_input(symbol, as_of_date=as_of_date)

    upstream: dict[str, dict[str, Any]] = {}
    upstream["MarketRegimeAgent"] = market_regime_agent(ctx)
    upstream["TechnicalAgent"] = technical_agent(ctx)
    upstream["FundamentalAgent"] = fundamental_agent(ctx)
    upstream["SentimentAgent"] = sentiment_agent(ctx)
    upstream["BullResearcher"] = bull_researcher(ctx, upstream)
    upstream["BearResearcher"] = bear_researcher(ctx, upstream)
    upstream["RiskManager"] = risk_manager(ctx, upstream)
    upstream["PortfolioManager"] = portfolio_manager(ctx, upstream)
    final = final_advisor(ctx, upstream)

    result = {
        "symbol": symbol,
        "as_of_date": ctx["as_of_date"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "engine": "deterministic_rules_v1",
        "input_context": ctx,
        "agents": upstream,
        "final": final,
    }
    if persist:
        out_dir = ROOT / "artifacts" / "agents"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"agents_{symbol.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["artifact"] = str(path.relative_to(ROOT))
    return result
