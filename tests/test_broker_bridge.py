"""Broker bridge — Eastmoney launcher, unified routing, session status."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from gateway.brokers.eastmoney_launcher import build_urls, launch_broker, symbol_to_eastmoney_code
from gateway.brokers.unified_bridge import broker_session_status, place_real_order
from gateway.brokers.xtquant_bridge import detect_miniqmt_paths, xtquant_available
from gateway.live_trading.gates import LiveTradingGates


class TestEastmoneyLauncher(unittest.TestCase):
    def test_symbol_sh(self):
        m, c = symbol_to_eastmoney_code("600000.SH")
        self.assertEqual((m, c), ("sh", "600000"))

    def test_symbol_sz(self):
        m, c = symbol_to_eastmoney_code("000001.SZ")
        self.assertEqual((m, c), ("sz", "000001"))

    def test_build_urls_quote(self):
        urls = build_urls(symbol="600000.SH", name="浦发银行")
        self.assertIn("quote", urls)
        self.assertIn("sh600000", urls["quote"])
        self.assertEqual(urls["trade_login"], "https://jywg.eastmoneysec.com/")

    @patch("gateway.brokers.broker_launcher.webbrowser.open", return_value=True)
    def test_launch_trade_login(self, mock_open):
        r = launch_broker(target="trade_login")
        self.assertTrue(r["ok"])
        self.assertEqual(r["url"], "https://jywg.eastmoneysec.com/")
        mock_open.assert_called_once()


class TestCnBrokerRegistry(unittest.TestCase):
    def test_huatai_urls(self):
        from gateway.brokers.broker_launcher import build_broker_urls
        urls = build_broker_urls("huatai_zhangle", symbol="600000.SH")
        self.assertIn("service.htsc.com.cn", urls["trade_login"])
        self.assertIn("quote", urls)

    @patch("gateway.brokers.broker_launcher.webbrowser.open", return_value=True)
    def test_huatai_launch(self, _mock):
        from gateway.brokers.broker_launcher import launch_cn_broker
        r = launch_cn_broker("huatai_zhangle", target="trade_login")
        self.assertTrue(r["ok"])
        self.assertIn("涨乐", r["broker_label"])


class TestUnifiedBridge(unittest.TestCase):
    def test_session_status_shape(self):
        s = broker_session_status()
        self.assertIn("active_broker", s)
        self.assertIn("xtquant", s)
        self.assertIn("gates", s)

    @patch("gateway.brokers.execution_router.launch_cn_broker")
    @patch("gateway.brokers.execution_router.can_submit_live_order")
    @patch("gateway.brokers.execution_router.load_broker_config")
    @patch("gateway.live_trading.gates.load_gates")
    def test_eastmoney_browser_path(self, mock_gates, mock_cfg, mock_gate, mock_launch):
        from gateway.brokers.connection_manager import BrokerConfig

        mock_gates.return_value = LiveTradingGates()
        mock_cfg.return_value = BrokerConfig(active_broker="eastmoney_manual")
        mock_gate.return_value = {"allowed": True, "blockers": [], "gates": {}}
        mock_launch.return_value = {
            "ok": True,
            "url": "https://jywg.eastmoneysec.com/",
            "broker_label": "东方财富证券",
            "urls": {"quote": "https://quote.eastmoney.com/sh600000.html"},
            "next_steps": ["登录", "买入"],
            "message": "已打开",
        }
        with patch(
            "gateway.brokers.execution_router.list_execution_paths",
            return_value=[{
                "path_id": "browser_launch",
                "unattended_capable": False,
                "priority": 99,
            }],
        ):
            r = place_real_order(
                symbol="600000.SH",
                name="浦发银行",
                side="BUY",
                quantity=100,
                limit_price=10.5,
                user_confirmed=True,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["handoff"]["mode"], "browser_launch")
        self.assertEqual(r["handoff"]["web_url"], "https://jywg.eastmoneysec.com/")

    @patch("gateway.brokers.execution_router.can_submit_live_order")
    @patch("gateway.live_trading.gates.load_gates")
    def test_gate_blocks_order(self, mock_gates, mock_gate):
        mock_gates.return_value = LiveTradingGates()
        mock_gate.return_value = {
            "allowed": False,
            "blockers": ["REAL_MONEY_DISABLED"],
            "gates": {"real_money_enabled": False},
        }
        r = place_real_order(
            symbol="600000.SH",
            name="",
            side="BUY",
            quantity=100,
            limit_price=10.0,
            user_confirmed=True,
        )
        self.assertFalse(r["ok"])
        self.assertIn("REAL_MONEY_DISABLED", r["blockers"])


class TestXtQuantBridge(unittest.TestCase):
    def test_detect_paths_returns_list(self):
        paths = detect_miniqmt_paths()
        self.assertIsInstance(paths, list)

    def test_xtquant_unavailable_without_path(self):
        with patch.dict("os.environ", {}, clear=True):
            avail = xtquant_available("")
        if not avail["available"]:
            self.assertIn("reason", avail)
            self.assertIn("install_url", avail)


if __name__ == "__main__":
    unittest.main()
