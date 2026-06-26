"""Phase 1 infrastructure tests — envelope, paper RBAC, ticket generation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestEnvelopePhase1(unittest.TestCase):
    def test_error_includes_user_action_and_retryable(self) -> None:
        from gateway.api.envelope import envelope_err

        out = envelope_err(
            "PAPER_ENGINE_START_FAILED",
            "模拟交易引擎启动失败",
            user_action="请使用 admin 登录",
            retryable=True,
            details={"reason": "forbidden"},
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "PAPER_ENGINE_START_FAILED")
        self.assertEqual(out["error"]["user_action"], "请使用 admin 登录")
        self.assertTrue(out["error"]["retryable"])
        self.assertIn("request_id", out)
        self.assertIn("trace_id", out)


class TestPaperStartRBAC(unittest.TestCase):
    def test_viewer_gets_structured_envelope_not_exception(self) -> None:
        from fastapi.testclient import TestClient

        from gateway.api.app import app

        client = TestClient(app)
        res = client.post(
            "/api/v1/paper/start",
            headers={"X-API-Key": "svc-portal-read"},
            json={},
        )
        self.assertEqual(res.status_code, 403)
        body = res.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"]["code"], "PAPER_ENGINE_START_FAILED")
        self.assertIn("user_action", body["error"])
        self.assertTrue(body["error"]["retryable"])

    def test_admin_starts_paper(self) -> None:
        from fastapi.testclient import TestClient

        from gateway.api.app import app

        client = TestClient(app)
        res = client.post(
            "/api/v1/paper/start",
            headers={"X-API-Key": "demo-local-key-change-in-prod"},
            json={},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["data"]["status"], "PAPER_TRADING_ACTIVE")


class TestHealthEndpoint(unittest.TestCase):
    def test_health_includes_data_gate(self) -> None:
        from fastapi.testclient import TestClient

        from gateway.api.app import app

        client = TestClient(app)
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("data_gate_verdict", body)
        self.assertIn("mode", body)


class TestTicketGeneration(unittest.TestCase):
    def test_ticket_eod_returns_lines_or_actionable_blockers(self) -> None:
        from gateway.autopilot import generate_order_ticket

        data = generate_order_ticket(preset="balanced", top_n=5, mode="eod")
        self.assertIn("ticket_id", data)
        self.assertIn("status", data)
        if data["status"] == "NO_EXECUTABLE_LINES":
            self.assertTrue(data.get("blockers"))
            self.assertIn("user_action", data)
            self.assertTrue(data.get("retryable"))
        elif data["status"] == "BLOCKED":
            self.assertTrue(data.get("blockers"))
        else:
            self.assertGreater(len(data.get("lines", [])), 0)


if __name__ == "__main__":
    unittest.main()
