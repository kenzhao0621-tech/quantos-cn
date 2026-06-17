"""QuantOS CN multi-agent research workflow — advisory only, no execution bypass."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "data" / "gateway" / "agent_runs"


@dataclass
class AgentEvidence:
    agent_id: str
    claim: str
    evidence: list[str] = field(default_factory=list)
    counterevidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    missing_data: list[str] = field(default_factory=list)
    artifact_pointers: list[str] = field(default_factory=list)


@dataclass
class AgentRunResult:
    run_id: str
    as_of: str
    agents: list[dict[str, Any]]
    bull_summary: str
    bear_summary: str
    risk_verdict: str
    portfolio_verdict: str
    candidate_gate: str
    execution_allowed: bool = False
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_warehouse_freshness() -> dict[str, Any]:
    db = ROOT / "data" / "warehouse" / "quant.duckdb"
    return {"warehouse_exists": db.exists(), "path": str(db)}


def _fundamental_analyst(as_of: str) -> AgentEvidence:
    ev = AgentEvidence(
        agent_id="FundamentalAnalystCN",
        claim="基本面数据可用性检查",
        confidence=0.6 if _load_warehouse_freshness()["warehouse_exists"] else 0.1,
    )
    if ev.confidence > 0.5:
        ev.evidence.append("DuckDB warehouse present")
        ev.artifact_pointers.append(str(ROOT / "data" / "warehouse" / "quant.duckdb"))
    else:
        ev.missing_data.append("warehouse")
        ev.counterevidence.append("BLOCKED_BY_DATA")
    return ev


def _technical_analyst(as_of: str) -> AgentEvidence:
    idx_dir = ROOT / "data" / "indices"
    has_idx = idx_dir.exists() and any(idx_dir.glob("*.json"))
    return AgentEvidence(
        agent_id="TechnicalAnalystCN",
        claim="技术/指数快照",
        confidence=0.7 if has_idx else 0.2,
        evidence=[f"indices_count={len(list(idx_dir.glob('*.json')))}"] if has_idx else [],
        missing_data=[] if has_idx else ["indices"],
    )


def _disclosure_analyst(as_of: str) -> AgentEvidence:
    disc = ROOT / "data" / "disclosures"
    has = disc.exists() and any(disc.rglob("*.json"))
    return AgentEvidence(
        agent_id="DisclosureAnalystCN",
        claim="公告披露覆盖",
        confidence=0.65 if has else 0.15,
        evidence=["CNINFO disclosures ingested"] if has else [],
        missing_data=[] if has else ["disclosures"],
    )


def _bull_researcher(signals: list[str]) -> AgentEvidence:
    return AgentEvidence(
        agent_id="BullResearcherCN",
        claim="多头论点",
        confidence=0.55,
        evidence=signals or ["暂无强信号"],
    )


def _bear_researcher(risks: list[str]) -> AgentEvidence:
    return AgentEvidence(
        agent_id="BearResearcherCN",
        claim="空头/风险论点",
        confidence=0.6,
        evidence=risks or ["T+1 约束", "涨跌停风险", "数据新鲜度风险"],
    )


def _risk_officer(blockers: list[str]) -> AgentEvidence:
    halted = any("BLOCKED" in b or "HALT" in b.upper() for b in blockers)
    return AgentEvidence(
        agent_id="RiskOfficerCN",
        claim="风险官审核",
        confidence=0.9,
        evidence=["PAPER_TRADING_ONLY", "REAL_MONEY_DISABLED"],
        counterevidence=blockers,
        missing_data=blockers,
    )


def run_agent_research(*, as_of: str, run_id: str = "") -> AgentRunResult:
    """Controlled multi-agent research — outputs advisory artifacts only."""
    run_id = run_id or str(uuid.uuid4())[:12]
    fund = _fundamental_analyst(as_of)
    tech = _technical_analyst(as_of)
    disc = _disclosure_analyst(as_of)
    blockers = fund.missing_data + tech.missing_data + disc.missing_data

    bull = _bull_researcher([e for e in fund.evidence + tech.evidence if e])
    bear = _bear_researcher(blockers + ["累计亏损上限 ¥1,000"])

    risk = _risk_officer(blockers)
    risk_verdict = "REJECT" if blockers else "PASS_WITH_CAUTION"

    from gateway.portfolio.constructor import construct_portfolio
    proposal = construct_portfolio(run_id=run_id, as_of_date=as_of, ranked_symbols=[("600000.SH", 70.0)])
    portfolio_verdict = "NO_TRADE" if blockers else ("TRADE_CANDIDATE" if proposal.candidates else "NO_TRADE")

    result = AgentRunResult(
        run_id=run_id,
        as_of=as_of,
        agents=[asdict(a) for a in [fund, tech, disc, bull, bear, risk]],
        bull_summary=bull.claim + ": " + "; ".join(bull.evidence[:3]),
        bear_summary=bear.claim + ": " + "; ".join(bear.evidence[:3]),
        risk_verdict=risk_verdict,
        portfolio_verdict=portfolio_verdict,
        candidate_gate="BLOCKED_BY_DATA" if blockers else "CANDIDATE_DATA_READY",
        execution_allowed=False,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{run_id}.json"
    path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return result
