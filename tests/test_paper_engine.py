"""Paper trading engine tests — T+1, lots, partial fill, restart."""

from __future__ import annotations

import unittest
from pathlib import Path

from gateway.config import ROOT
from gateway.paper.engine import PaperOrderState, PaperTradingEngine
from gateway.risk.engine import OrderIntent, RiskEngine
from gateway.risk.kill_switch import KillSwitch
from gateway.config import GatewayConfig


class TestPaperEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.events = ROOT / "data" / "gateway" / "paper_events.jsonl"
        self.orders = ROOT / "data" / "gateway" / "paper_orders.json"
        for p in (self.events, self.orders):
            if p.exists():
                p.unlink()

    def _intent(self, **kw) -> OrderIntent:
        qty = int(kw.get("quantity", 100))
        price = float(kw.get("limit_price", 10.0))
        return OrderIntent(
            client_order_id=kw.get("client_order_id", "test-1"),
            symbol=kw.get("symbol", "600000.SH"),
            side=kw.get("side", "BUY"),
            quantity=qty,
            limit_price=price,
            notional_cny=price * qty,
            run_id=kw.get("run_id", ""),
            strategy_id=kw.get("strategy_id", ""),
            model_id=kw.get("model_id", ""),
        )

    def _engine(self) -> PaperTradingEngine:
        cfg = GatewayConfig.load()
        risk = RiskEngine(cfg, KillSwitch())
        risk.set_mode("PAPER_TRADING")
        return PaperTradingEngine(risk, capital_cny=5000.0)

    def test_invalid_buy_lot_rejected(self) -> None:
        eng = self._engine()
        o = eng.submit(self._intent(quantity=50, limit_price=10.0))
        self.assertEqual(o.state, PaperOrderState.REJECTED)
        self.assertIn("INVALID_LOT", o.reject_reason)

    def test_insufficient_cash(self) -> None:
        eng = self._engine()
        o = eng.submit(self._intent(quantity=600, limit_price=10.0))
        self.assertIn(o.state, (PaperOrderState.REJECTED, PaperOrderState.RISK_REJECTED))
        self.assertTrue(
            o.reject_reason in ("INSUFFICIENT_CASH", "single_name_risk_exceeded")
            or "CASH" in o.reject_reason
            or "risk" in o.reject_reason
        )

    def test_t1_sell_blocked_same_day(self) -> None:
        eng = self._engine()
        buy = eng.submit(self._intent(side="BUY", quantity=100, limit_price=10.0))
        self.assertEqual(buy.state, PaperOrderState.FILLED)
        sell = eng.submit(self._intent(side="SELL", quantity=100, limit_price=10.0, client_order_id="sell-1"))
        self.assertEqual(sell.state, PaperOrderState.REJECTED)
        self.assertIn("T_PLUS_1", sell.reject_reason)

    def test_t1_sell_after_settlement(self) -> None:
        eng = self._engine()
        eng.submit(self._intent(side="BUY", quantity=100, limit_price=10.0))
        eng.settle_t_plus_1("600000.SH")
        sell = eng.submit(self._intent(side="SELL", quantity=100, limit_price=10.0, client_order_id="sell-2"))
        self.assertEqual(sell.state, PaperOrderState.FILLED)

    def test_idempotency_duplicate(self) -> None:
        eng = self._engine()
        intent = self._intent(side="BUY", quantity=100, limit_price=10.0, client_order_id="dup-1")
        o1 = eng.submit(intent, idempotency_key="dup-1")
        o2 = eng.submit(intent, idempotency_key="dup-1")
        self.assertEqual(o1.order_id, o2.order_id)

    def test_partial_fill(self) -> None:
        eng = self._engine()
        o = eng.submit(self._intent(side="BUY", quantity=100, limit_price=10.0), fill_ratio=0.5)
        self.assertEqual(o.filled_qty, 50)
        self.assertIn(o.state, (PaperOrderState.PARTIALLY_FILLED, PaperOrderState.FILLED))

    def test_restart_recovery(self) -> None:
        eng = self._engine()
        eng.submit(self._intent(side="BUY", quantity=100, limit_price=10.0))
        cfg = GatewayConfig.load()
        risk = RiskEngine(cfg, KillSwitch())
        risk.set_mode("PAPER_TRADING")
        eng2 = PaperTradingEngine(risk, capital_cny=5000.0)
        self.assertGreaterEqual(len(eng2.orders), 1)


if __name__ == "__main__":
    unittest.main()
