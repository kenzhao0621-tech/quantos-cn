"""AgentsOS roles — 9 deterministic rule agents over structured JSON.

Output contract (§7.3): agent, rating, score, confidence, key_points, risks,
evidence_refs, must_not_trade, degraded. Rules read ONLY the input JSON.
"""

from __future__ import annotations

from typing import Any


def _out(agent: str, *, rating: str, score: float, confidence: float,
         key_points: list[str], risks: list[str] | None = None,
         evidence_refs: list[str] | None = None, must_not_trade: bool = False,
         degraded: bool = False) -> dict[str, Any]:
    return {
        "agent": agent,
        "rating": rating,
        "score": round(max(-1.0, min(1.0, score)), 3),
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "key_points": key_points,
        "risks": risks or [],
        "evidence_refs": evidence_refs or [],
        "must_not_trade": must_not_trade,
        "degraded": degraded,
        "engine": "deterministic_rules_v1",
    }


def market_regime_agent(ctx: dict[str, Any]) -> dict[str, Any]:
    regime = ctx.get("market_regime") or {}
    if regime.get("degraded"):
        return _out("MarketRegimeAgent", rating="neutral", score=0.0, confidence=0.1,
                    key_points=["指数数据不足，无法判断大盘状态"], degraded=True)
    score = float(regime.get("score") or 0)
    rating = "positive" if score > 0.2 else ("negative" if score < -0.2 else "neutral")
    return _out(
        "MarketRegimeAgent", rating=rating, score=score, confidence=0.7,
        key_points=[
            f"大盘状态 {regime.get('regime')}（{regime.get('index_code')}）",
            f"20日收益 {regime.get('ret_20d_pct')}%，年化波动 {regime.get('annualized_vol_pct')}%",
        ],
        evidence_refs=[f"index_bars:{regime.get('index_code')}"],
    )


def technical_agent(ctx: dict[str, Any]) -> dict[str, Any]:
    m = ctx.get("market_data_summary") or {}
    f = ctx.get("factor_signal") or {}
    k = ctx.get("kronos_signal") or {}
    if not m.get("available"):
        return _out("TechnicalAgent", rating="blocked", score=0.0, confidence=0.0,
                    key_points=["无行情数据"], must_not_trade=True, degraded=True)
    pts, score = [], 0.0
    ret20 = m.get("ret_20d_pct")
    if ret20 is not None:
        pts.append(f"20日动量 {ret20}%")
        score += max(-0.5, min(0.5, ret20 / 40.0))
    pts.append("站上MA20" if m.get("above_ma20") else "位于MA20下方")
    score += 0.15 if m.get("above_ma20") else -0.15
    kscore = float(k.get("score") or 0)
    kconf = float(k.get("confidence") or 0)
    if not k.get("degraded"):
        pts.append(f"Kronos 5日信号 {kscore:+.2f}（置信 {kconf:.2f}）")
        score += kscore * 0.4
    else:
        pts.append("Kronos 不可用/降级，仅用传统技术信号")
    risks = []
    vol = m.get("annualized_vol_pct")
    if vol and vol > 50:
        risks.append(f"年化波动率高（{vol}%）")
        score -= 0.15
    rating = "positive" if score > 0.15 else ("negative" if score < -0.15 else "neutral")
    conf = 0.55 + (0.2 * kconf if not k.get("degraded") else 0.0)
    return _out("TechnicalAgent", rating=rating, score=score, confidence=conf,
                key_points=pts, risks=risks,
                evidence_refs=[f"daily_bars:{ctx['symbol']}", "kronos_signal"],
                degraded=bool(k.get("degraded")))


def fundamental_agent(ctx: dict[str, Any]) -> dict[str, Any]:
    f = ctx.get("fundamental_summary") or {}
    if not f.get("available"):
        return _out("FundamentalAgent", rating="neutral", score=0.0, confidence=0.1,
                    key_points=["无基本面快照（fundamental 表缺该股票）"], degraded=True)
    pts, risks, score = [], [], 0.0
    pe, pb = f.get("pe_ttm"), f.get("pb")
    if pe is not None:
        if 0 < pe < 20:
            pts.append(f"PE(TTM) {pe} 偏低")
            score += 0.25
        elif pe > 60:
            risks.append(f"PE(TTM) {pe} 偏高")
            score -= 0.25
        elif pe <= 0:
            risks.append("PE 为负（亏损）")
            score -= 0.35
        else:
            pts.append(f"PE(TTM) {pe} 中性区间")
    if pb is not None and pb < 1.0:
        pts.append(f"PB {pb} 破净")
        score += 0.1
    rating = "positive" if score > 0.15 else ("negative" if score < -0.15 else "neutral")
    return _out("FundamentalAgent", rating=rating, score=score, confidence=0.5,
                key_points=pts or ["估值指标中性"], risks=risks,
                evidence_refs=[f"fundamental:{ctx['symbol']}@{f.get('as_of')}"])


def sentiment_agent(ctx: dict[str, Any]) -> dict[str, Any]:
    news = ctx.get("news_summary") or []
    if not news:
        return _out("SentimentAgent", rating="neutral", score=0.0, confidence=0.2,
                    key_points=["近期无官方披露记录（仅覆盖官方披露源，非全网舆情）"], degraded=True)
    neg_kw = ("退市", "违规", "处罚", "警示", "立案", "减持", "质押", "诉讼", "停牌")
    pos_kw = ("回购", "增持", "中标", "分红", "业绩预增")
    score, pts = 0.0, []
    for n in news[:5]:
        title = str(n.get("title") or "")
        tag = ""
        if any(k in title for k in neg_kw):
            score -= 0.3
            tag = "[负面]"
        elif any(k in title for k in pos_kw):
            score += 0.2
            tag = "[正面]"
        pts.append(f"{tag}{title[:40]}（{n.get('source')} {str(n.get('published_at'))[:10]}）")
    rating = "positive" if score > 0.15 else ("negative" if score < -0.15 else "neutral")
    return _out("SentimentAgent", rating=rating, score=score, confidence=0.4,
                key_points=pts, evidence_refs=[str(n.get("url")) for n in news[:5] if n.get("url")])


def bull_researcher(ctx: dict[str, Any], upstream: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pts = []
    for name in ("TechnicalAgent", "FundamentalAgent", "SentimentAgent", "MarketRegimeAgent"):
        a = upstream.get(name) or {}
        if a.get("score", 0) > 0:
            pts.extend(f"{name}: {p}" for p in a.get("key_points", [])[:2])
    score = sum(max(0.0, upstream.get(n, {}).get("score", 0)) for n in upstream) / max(len(upstream), 1)
    return _out("BullResearcher", rating="positive" if pts else "neutral",
                score=score, confidence=0.5,
                key_points=pts or ["未发现有力看多依据"],
                evidence_refs=["upstream_agents"])


def bear_researcher(ctx: dict[str, Any], upstream: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pts = [f"风险标记: {f}" for f in (ctx.get("risk_flags") or [])[:4]]
    for name, a in upstream.items():
        if a.get("score", 0) < 0:
            pts.extend(f"{name}: {p}" for p in (a.get("risks") or a.get("key_points", []))[:2])
        pts.extend(f"{name}: {r}" for r in a.get("risks", [])[:2])
    score = -sum(abs(min(0.0, upstream.get(n, {}).get("score", 0))) for n in upstream) / max(len(upstream), 1)
    if ctx.get("risk_flags"):
        score -= 0.1 * len(ctx["risk_flags"])
    return _out("BearResearcher", rating="negative" if pts else "neutral",
                score=score, confidence=0.5,
                key_points=list(dict.fromkeys(pts)) or ["未发现显著风险点"],
                evidence_refs=["risk_flags", "upstream_agents"])


HARD_BLOCK_FLAGS = {"SUSPENDED", "NO_MARKET_DATA", "INVALID_PRICE", "LIMIT_UP_NO_ENTRY", "LIMIT_DOWN"}


def risk_manager(ctx: dict[str, Any], upstream: dict[str, dict[str, Any]]) -> dict[str, Any]:
    flags = set(ctx.get("risk_flags") or [])
    hard = flags & HARD_BLOCK_FLAGS
    ev = ctx.get("backtest_evidence") or {}
    bt = (ev.get("latest_backtest") or {})
    pts, risks = [], []
    must_not = bool(hard)
    if hard:
        risks.append(f"硬性阻断: {sorted(hard)}")
    if "ST_OR_RISKY_BOARD" in flags:
        risks.append("ST 或高风险板块")
    if "HIGH_VOLATILITY" in flags:
        risks.append("高波动")
    if "LOW_LIQUIDITY" in flags:
        risks.append("流动性不足")
        must_not = True
    if bt.get("status") == "NOT_RUN":
        risks.append("回测证据缺失（NOT_RUN）— 建议先跑 quick 回测")
    elif bt.get("gate") == "BLOCKED_BY_VALIDATION":
        risks.append("策略未通过验证门（BLOCKED_BY_VALIDATION）")
    pts.append(f"风险标记 {len(flags)} 项；回测状态 {bt.get('status')}")
    score = -0.2 * len(risks)
    return _out("RiskManager", rating="blocked" if must_not else ("negative" if risks else "neutral"),
                score=score, confidence=0.8,
                key_points=pts, risks=risks,
                evidence_refs=["risk_flags", "artifacts/backtests"],
                must_not_trade=must_not)


def portfolio_manager(ctx: dict[str, Any], upstream: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rm = upstream.get("RiskManager") or {}
    if rm.get("must_not_trade"):
        return _out("PortfolioManager", rating="blocked", score=-1.0, confidence=0.9,
                    key_points=["风险经理否决——不给出仓位建议"], must_not_trade=True)
    composite = sum(upstream.get(n, {}).get("score", 0) for n in
                    ("TechnicalAgent", "FundamentalAgent", "SentimentAgent", "MarketRegimeAgent")) / 4
    max_pos = 0.10 if composite > 0.2 else (0.05 if composite > 0 else 0.0)
    pts = [
        f"综合信号 {composite:+.2f}",
        f"单票仓位上限 {max_pos * 100:.0f}%（组合层面再受行业 30% 限制）",
        "T+1：今日买入次一交易日方可卖出",
    ]
    return _out("PortfolioManager", rating="positive" if max_pos > 0 else "neutral",
                score=composite, confidence=0.6, key_points=pts,
                evidence_refs=["upstream_agents", "risk_limits"])
