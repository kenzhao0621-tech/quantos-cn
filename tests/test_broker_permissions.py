"""Broker API permissions — investor role must not receive 403 on connect flows."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

INVESTOR_KEY = "dev-investor-key"
VIEWER_KEY = "svc-portal-read"


class TestBrokerPermissions(unittest.TestCase):
    def _client(self):
        from fastapi.testclient import TestClient

        from gateway.api.app import app

        return TestClient(app)

    def test_investor_connect_flow_not_forbidden(self) -> None:
        client = self._client()
        with patch(
            "gateway.brokers.broker_autopilot.run_connect_flow",
            return_value={
                "ok": True,
                "broker_id": "eastmoney_manual",
                "client_url": "https://jywg.eastmoneysec.com/",
                "ready_for_trade": False,
                "message": "已打开登录页",
            },
        ):
            res = client.post(
                "/api/v1/brokers/connect-flow",
                headers={"X-API-Key": INVESTOR_KEY},
                json={"broker_id": "eastmoney_manual", "open_login": True, "sync_watchlist": False},
            )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["ok"], body)
        self.assertIn("client_url", body["data"])

    def test_viewer_connect_flow_forbidden(self) -> None:
        client = self._client()
        res = client.post(
            "/api/v1/brokers/connect-flow",
            headers={"X-API-Key": VIEWER_KEY},
            json={"broker_id": "eastmoney_manual", "open_login": True},
        )
        self.assertEqual(res.status_code, 403)

    def test_investor_onboarding_beginner(self) -> None:
        client = self._client()
        res = client.get("/api/v1/onboarding/beginner", headers={"X-API-Key": INVESTOR_KEY})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertGreaterEqual(len(body["data"]["steps"]), 4)
        self.assertTrue(body["data"]["disclaimer"]["no_auto_real_orders"])

    def test_investor_broker_ecosystem(self) -> None:
        client = self._client()
        res = client.get("/api/v1/brokers/ecosystem", headers={"X-API-Key": INVESTOR_KEY})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertTrue(len(body["data"].get("brokers", [])) >= 1)

    def test_investor_execution_paths(self) -> None:
        client = self._client()
        res = client.get("/api/v1/brokers/execution-paths", headers={"X-API-Key": INVESTOR_KEY})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertTrue(len(body["data"].get("paths", [])) >= 1)

    def test_investor_live_gates_user_risk(self) -> None:
        client = self._client()
        res = client.put(
            "/api/v1/live-trading/gates",
            headers={"X-API-Key": INVESTOR_KEY},
            json={"user_confirmed_risk": True, "real_money_enabled": False},
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()["ok"])

    def test_login_redirect_token(self) -> None:
        client = self._client()
        res = client.post(
            "/api/v1/brokers/connect-flow",
            headers={"X-API-Key": INVESTOR_KEY},
            json={"broker_id": "huatai_zhangle", "open_login": True, "assist_login": False},
        )
        self.assertEqual(res.status_code, 200, res.text)
        token = res.json()["data"].get("login_redirect_token")
        self.assertTrue(token)
        r2 = client.get(f"/api/v1/brokers/login-redirect/{token}", follow_redirects=False)
        self.assertEqual(r2.status_code, 302)
        self.assertIn("zhangle.com", r2.headers.get("location", ""))

    def test_investor_paper_start(self) -> None:
        client = self._client()
        res = client.post("/api/v1/paper/start", headers={"X-API-Key": INVESTOR_KEY}, json={})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()["ok"])


if __name__ == "__main__":
    unittest.main()
