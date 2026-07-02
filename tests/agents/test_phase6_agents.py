"""Phase 6 AgentsOS tests — JSON contracts, veto, ratings, honesty."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

OUTPUT_KEYS = {"agent", "rating", "score", "confidence", "key_points", "risks",
               "evidence_refs", "must_not_trade", "degraded"}


def _ctx(**over):
    base = {
        "as_of_date": "2026-07-01",
        "symbol": "600000.SH",
        "sector": {"available": True, "name": "浦发银行", "sector": "银行"},
        "market_data_summary": {
            "available": True, "as_of": "2026-07-01", "close": 10.0, "pct_chg": 1.0,
            "ret_20d_pct": 5.0, "ret_60d_pct": 12.0, "annualized_vol_pct": 25.0,
            "above_ma20": True, "avg_amount_20d": 500000.0, "suspended_today": False,
            "bars": 61,
        },
        "market_regime": {"regime": "BULL_TREND", "score": 0.8, "degraded": False,
                          "index_code": "000300.SH", "ret_20d_pct": 2.0, "annualized_vol_pct": 18.0},
        "kronos_signal": {"score": 0.3, "confidence": 0.6, "degraded": False},
        "factor_signal": {"available": True, "momentum_20d_pct": 5.0, "above_ma20": True, "score": 0.4},
        "fundamental_summary": {"available": True, "as_of": "20260630", "pe_ttm": 8.0, "pb": 0.9},
        "news_summary": [],
        "risk_flags": [],
        "backtest_evidence": {"latest_backtest": {"status": "OK", "gate": "CANDIDATE_POOL_ELIGIBLE"},
                              "model_validation": {"verdict": "PASS"}},
        "constraints": {"market": "A-share", "t_plus_1": True, "price_limit": True,
                        "paper_trading_only": True},
    }
    base.update(over)
    return base


def _run_all(ctx):
    from gateway.agents.quantos.roles import (
        bear_researcher, bull_researcher, fundamental_agent, market_regime_agent,
        portfolio_manager, risk_manager, sentiment_agent, technical_agent,
    )

    up = {}
    up["MarketRegimeAgent"] = market_regime_agent(ctx)
    up["TechnicalAgent"] = technical_agent(ctx)
    up["FundamentalAgent"] = fundamental_agent(ctx)
    up["SentimentAgent"] = sentiment_agent(ctx)
    up["BullResearcher"] = bull_researcher(ctx, up)
    up["BearResearcher"] = bear_researcher(ctx, up)
    up["RiskManager"] = risk_manager(ctx, up)
    up["PortfolioManager"] = portfolio_manager(ctx, up)
    return up


class TestAgentContracts(unittest.TestCase):
    def test_all_agents_emit_contract_fields(self):
        up = _run_all(_ctx())
        self.assertEqual(len(up), 8)
        for name, out in up.items():
            self.assertTrue(OUTPUT_KEYS.issubset(out.keys()), f"{name} missing keys {OUTPUT_KEYS - set(out.keys())}")
            self.assertIn(out["rating"], ("positive", "neutral", "negative", "blocked"))
            self.assertGreaterEqual(out["score"], -1.0)
            self.assertLessEqual(out["score"], 1.0)

    def test_final_advisor_grades(self):
        from gateway.agents.quantos.pipeline import final_advisor

        ctx = _ctx()
        final = final_advisor(ctx, _run_all(ctx))
        self.assertIn(final["rating"], ("A", "B", "C", "D", "BLOCKED"))
        self.assertIn("invalidation_conditions", final)
        self.assertIn("bull_case", final)
        self.assertIn("bear_case", final)
        self.assertIn("不构成投资建议", final["disclaimer"])


class TestRiskManagerVeto(unittest.TestCase):
    def test_suspended_is_vetoed(self):
        ctx = _ctx(risk_flags=["SUSPENDED"])
        up = _run_all(ctx)
        self.assertTrue(up["RiskManager"]["must_not_trade"])
        from gateway.agents.quantos.pipeline import final_advisor

        final = final_advisor(ctx, up)
        self.assertEqual(final["rating"], "BLOCKED")

    def test_low_liquidity_is_vetoed(self):
        ctx = _ctx(risk_flags=["LOW_LIQUIDITY"])
        up = _run_all(ctx)
        self.assertTrue(up["RiskManager"]["must_not_trade"])

    def test_portfolio_manager_respects_veto(self):
        ctx = _ctx(risk_flags=["SUSPENDED"])
        up = _run_all(ctx)
        self.assertTrue(up["PortfolioManager"]["must_not_trade"])


class TestHonesty(unittest.TestCase):
    def test_no_market_data_blocks(self):
        ctx = _ctx(market_data_summary={"available": False, "reason": "no_bars"},
                   risk_flags=["NO_MARKET_DATA"])
        up = _run_all(ctx)
        self.assertEqual(up["TechnicalAgent"]["rating"], "blocked")
        self.assertTrue(up["RiskManager"]["must_not_trade"])

    def test_degraded_kronos_labeled(self):
        ctx = _ctx(kronos_signal={"score": 0.0, "confidence": 0.0, "degraded": True, "reason": "x"})
        up = _run_all(ctx)
        self.assertTrue(up["TechnicalAgent"]["degraded"])

    def test_no_forbidden_promises(self):
        import json

        ctx = _ctx()
        up = _run_all(ctx)
        from gateway.agents.quantos.pipeline import final_advisor

        blob = json.dumps({**up, "final": final_advisor(ctx, up)}, ensure_ascii=False)
        for banned in ("保证收益", "稳赚", "必涨", "无风险", "100%胜率", "放心梭哈"):
            self.assertNotIn(banned, blob)

    def test_missing_backtest_flagged(self):
        ctx = _ctx(backtest_evidence={"latest_backtest": {"status": "NOT_RUN"},
                                      "model_validation": {"verdict": "NOT_RUN"}})
        up = _run_all(ctx)
        self.assertTrue(any("回测证据缺失" in r for r in up["RiskManager"]["risks"]))

    def test_sentiment_requires_sources(self):
        ctx = _ctx(news_summary=[{"title": "回购公告", "source": "SSE",
                                  "published_at": "2026-06-30", "url": "https://sse.example/1"}])
        up = _run_all(ctx)
        self.assertTrue(up["SentimentAgent"]["evidence_refs"])


if __name__ == "__main__":
    unittest.main()
