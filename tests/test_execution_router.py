"""Execution router multi-path tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from gateway.brokers.connection_manager import BrokerConfig, save_broker_config
from gateway.brokers.execution_router import execute_order, list_execution_paths
from gateway.live_trading.gates import save_gates


class TestExecutionRouter(unittest.TestCase):
    def test_list_paths_includes_sidecar_when_configured(self) -> None:
        save_broker_config({
            "active_broker": "mac_sidecar",
            "sidecar_url": "http://127.0.0.1:8799",
            "account_id": "123",
        })
        paths = list_execution_paths()
        ids = [p["path_id"] for p in paths]
        self.assertIn("remote_sidecar", ids)
        self.assertIn("browser_launch", ids)

    def test_unattended_blocked_without_gates(self) -> None:
        save_gates({
            "real_money_enabled": False,
            "unattended_auto_enabled": False,
            "execution_level": 2,
        })
        r = execute_order(
            symbol="600000.SH",
            name="浦发银行",
            side="BUY",
            quantity=100,
            limit_price=10.0,
            unattended=True,
        )
        self.assertFalse(r["ok"])
        self.assertIn("LIVE_ORDER_BLOCKED", r.get("error", {}).get("code", ""))

    @patch("gateway.brokers.execution_router.sidecar_place_order")
    @patch("gateway.brokers.execution_router.sidecar_configured", return_value=True)
    @patch("gateway.brokers.execution_router.test_sidecar_connection")
    def test_unattended_uses_sidecar_first(
        self, mock_test, mock_configured, mock_order
    ) -> None:
        save_broker_config({
            "active_broker": "mac_sidecar",
            "sidecar_url": "http://127.0.0.1:8799",
            "account_id": "123",
        })
        save_gates({
            "real_money_enabled": True,
            "user_confirmed_risk": True,
            "legal_review_passed": True,
            "unattended_auto_enabled": True,
            "execution_level": 3,
        })
        mock_test.return_value = {"connected": True, "status": "OK"}
        mock_order.return_value = {"ok": True, "order_id": 99, "message": "submitted"}

        from gateway.brokers.local_auth import save_consent
        save_consent("default", granted=True)

        r = execute_order(
            symbol="600000.SH",
            name="浦发银行",
            side="BUY",
            quantity=100,
            limit_price=10.0,
            user_id="default",
            unattended=True,
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r.get("winning_path"), "remote_sidecar")


if __name__ == "__main__":
    unittest.main()
