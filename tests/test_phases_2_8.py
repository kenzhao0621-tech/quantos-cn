"""Phases 2–8 integration tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestPhase2MarketGateway(unittest.TestCase):
    def test_gateway_health(self) -> None:
        from gateway.market_data_gateway import get_market_data_gateway
        h = get_market_data_gateway().health()
        self.assertIn("eod_tier", h)
        self.assertIn("live_tier", h)

    def test_data_quality_tier(self) -> None:
        from gateway.market_data_gateway import DataTier, get_market_data_gateway
        q = get_market_data_gateway().data_quality()
        self.assertIn(q.tier, list(DataTier))

    def test_diversity_constraints(self) -> None:
        from quant.screener.diversity import apply_diversity_constraints
        cands = [{"symbol": f"60000{i}.SH", "score": 10 - i, "sector": "银行" if i < 3 else "半导体", "last_close": 10 + i} for i in range(6)]
        selected, notes = apply_diversity_constraints(cands, top_n=3)
        self.assertLessEqual(len(selected), 3)


class TestPhase3Onboarding(unittest.TestCase):
    def test_strategy_proposals(self) -> None:
        from gateway.onboarding.profile import strategy_proposals
        props = strategy_proposals()
        self.assertEqual(len(props), 3)

    def test_beginner_report(self) -> None:
        from gateway.onboarding.profile import beginner_daily_summary
        r = beginner_daily_summary()
        self.assertIn("headline", r)
        self.assertIn("actions", r)


class TestPhase4Overfitting(unittest.TestCase):
    def test_dsr_and_pbo(self) -> None:
        from quant.validation.overfitting import deflated_sharpe_ratio, probability_backtest_overfitting
        dsr = deflated_sharpe_ratio(1.2, n_trials=10, n_obs=120)
        self.assertIn("dsr", dsr)
        pbo = probability_backtest_overfitting([[0.1, 0.2, -0.1], [0.05, 0.1, 0.0], [-0.1, 0.3, 0.2]])
        self.assertIn("pbo", pbo)


class TestPhase5PaperEngine(unittest.TestCase):
    def test_engine_lifecycle(self) -> None:
        from gateway.paper.engine import PaperRunState, load_engine_state, start_paper_engine, stop_paper_engine
        start = start_paper_engine(actor="test")
        self.assertTrue(start.get("ok") or start.get("blockers"))
        if start.get("ok"):
            state = load_engine_state()
            self.assertEqual(state.state, PaperRunState.RUNNING.value)
            stop = stop_paper_engine(actor="test")
            self.assertTrue(stop.get("ok"))


class TestPhase6BrokerGateway(unittest.TestCase):
    def test_gateway_adapters(self) -> None:
        from gateway.brokers.gateway import build_default_gateway
        from gateway.config import GatewayConfig
        from gateway.risk.engine import RiskEngine
        from gateway.risk.kill_switch import KillSwitch
        cfg = GatewayConfig.load()
        paper = __import__("gateway.brokers.paper", fromlist=["PaperBrokerAdapter"]).PaperBrokerAdapter(
            RiskEngine(cfg, KillSwitch(ROOT / "data" / "gateway" / "test_kill.json"))
        )
        gw = build_default_gateway(paper)
        health = gw.health_all()
        self.assertGreaterEqual(len(health), 3)


class TestPhase7LiveGates(unittest.TestCase):
    def test_live_order_blocked_by_default(self) -> None:
        from gateway.live_trading.gates import can_submit_live_order, save_gates
        save_gates({"user_confirmed_risk": False, "real_money_enabled": False})
        r = can_submit_live_order(notional_cny=1000.0)
        self.assertFalse(r["allowed"])
        self.assertIn("REAL_MONEY_DISABLED", r["blockers"])


class TestPhaseAPIs(unittest.TestCase):
    def test_onboarding_api(self) -> None:
        from fastapi.testclient import TestClient
        from gateway.api.app import app
        client = TestClient(app)
        res = client.get("/api/v1/onboarding/profile", headers={"X-API-Key": "demo-local-key-change-in-prod"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

    def test_market_gateway_api(self) -> None:
        from fastapi.testclient import TestClient
        from gateway.api.app import app
        client = TestClient(app)
        res = client.get("/api/v1/market/data-gateway/health", headers={"X-API-Key": "demo-local-key-change-in-prod"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("quality", res.json()["data"])


if __name__ == "__main__":
    unittest.main()
