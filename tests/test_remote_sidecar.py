"""Remote sidecar client tests."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from gateway.brokers.connection_manager import BrokerConfig, save_broker_config
from gateway.brokers.remote_sidecar import (
    sidecar_configured,
    sidecar_place_order,
    test_sidecar_connection,
)


class TestRemoteSidecar(unittest.TestCase):
    def test_not_configured(self):
        save_broker_config({"sidecar_url": "", "active_broker": "mac_sidecar"})
        self.assertFalse(sidecar_configured())
        r = test_sidecar_connection()
        self.assertEqual(r["status"], "SIDECAR_NOT_CONFIGURED")

    @patch("gateway.brokers.remote_sidecar.sidecar_request")
    def test_connected_session(self, mock_req):
        cfg = BrokerConfig(
            active_broker="mac_sidecar",
            sidecar_url="http://127.0.0.1:8799",
            account_id="123",
        )
        mock_req.side_effect = [
            {"ok": True, "backend": "xtquant"},
            {"ok": True, "status": "XTQUANT_CONNECTED", "real_orders": True, "message": "connected"},
        ]
        r = test_sidecar_connection(cfg)
        self.assertTrue(r["connected"])
        self.assertTrue(r["real_orders"])

    @patch("gateway.brokers.remote_sidecar.sidecar_request")
    def test_place_order(self, mock_req):
        mock_req.return_value = {"ok": True, "order_id": 42, "message": "submitted", "backend": "xtquant"}
        cfg = BrokerConfig(sidecar_url="http://127.0.0.1:8799")
        r = sidecar_place_order(
            symbol="600000.SH",
            side="BUY",
            quantity=100,
            limit_price=10.5,
            cfg=cfg,
        )
        self.assertTrue(r["ok"])
        mock_req.assert_called_once()
        args = mock_req.call_args
        self.assertEqual(args[0][0], "POST")
        self.assertEqual(args[0][1], "/v1/order")


if __name__ == "__main__":
    unittest.main()
