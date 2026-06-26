"""Screener enrichment, trade zones, and controlled live order handoff."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quant.screener.names import load_name_map, resolve_name
from quant.screener.trade_zones import compute_trade_zones
from quant.screener.beginner_guide import build_beginner_guide, build_detailed_reasons
from gateway.live_trading.gates import can_submit_live_order


class TestScreenerEnrichment(unittest.TestCase):
    def test_name_map_has_entries(self):
        names = load_name_map()
        self.assertGreater(len(names), 100)
        # sector file uses 6-digit codes mapped to SH/SZ
        sample = next((k for k in names if k.endswith(".SH")), "")
        if sample:
            self.assertTrue(resolve_name(sample))

    def test_trade_zones_ordered(self):
        z = compute_trade_zones(symbol="600000.SH", price=10.0, trend_pct=5.0, vol_20=2.5, last_pct=1.0)
        self.assertLessEqual(z["buy_zone_low"], z["buy_zone_high"])
        self.assertLess(z["stop_loss"], z["reference_price"])
        self.assertGreater(z["sell_zone_high"], z["reference_price"])
        self.assertIn("disclaimer", z)

    def test_beginner_guide_steps(self):
        z = compute_trade_zones(symbol="000001.SZ", price=12.0, trend_pct=3.0, vol_20=2.0)
        g = build_beginner_guide(
            symbol="000001.SZ",
            name="平安银行",
            price=12.0,
            qty=200,
            notional=2400.0,
            zones=z,
            reasons=["动量强"],
            data_as_of="2026-06-16",
            data_tier="EOD",
            broker_handoff="券商 App 确认",
        )
        self.assertGreaterEqual(len(g["steps"]), 5)
        self.assertIn("平安银行", g["summary"])

    def test_detailed_reasons_from_factors(self):
        rows = build_detailed_reasons(
            {"ret_20": 8.0, "avg_amount": 8e7, "pe": 12.5},
            [{"factor": "ret_20", "contribution": 0.12, "z_score": 1.5}],
        )
        self.assertTrue(any("动量" in r or "ret_20" in r or "20" in r for r in rows))


class TestLiveOrderGates(unittest.TestCase):
    def test_gates_block_without_confirm(self):
        result = can_submit_live_order(notional_cny=1000.0)
        if result["allowed"]:
            self.skipTest("gates already enabled in local config")
        self.assertIn("REAL_MONEY_DISABLED", result["blockers"] + result.get("blockers", []))

    @patch("gateway.brokers.live_order.ORDER_LOG")
    @patch("gateway.brokers.live_order.load_broker_config")
    @patch("gateway.brokers.live_order.can_submit_live_order")
    def test_submit_order_eastmoney_handoff(self, mock_gate, mock_cfg, mock_log):
        from gateway.brokers.connection_manager import BrokerConfig
        from gateway.brokers.live_order import submit_live_order

        mock_gate.return_value = {"allowed": True, "blockers": [], "gates": {}}
        mock_cfg.return_value = BrokerConfig(active_broker="eastmoney_manual", account_id="123")
        mock_log.parent.mkdir = lambda *a, **k: None
        mock_log.open.return_value.__enter__ = lambda s: s
        mock_log.open.return_value.__exit__ = lambda s, *a: None
        mock_log.open.return_value.write = lambda s: None

        out = submit_live_order(
            symbol="600000.SH",
            name="浦发银行",
            side="BUY",
            quantity=100,
            limit_price=10.5,
            user_confirmed=True,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["handoff"]["mode"], "manual_web")
        self.assertIn("steps", out["handoff"])


if __name__ == "__main__":
    unittest.main()
