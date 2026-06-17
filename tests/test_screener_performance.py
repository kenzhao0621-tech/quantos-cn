"""Screener performance — live mode must not block on network."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestScreenerPerformance(unittest.TestCase):
    def test_eod_mode_under_5_seconds(self) -> None:
        from fastapi.testclient import TestClient

        from gateway.api.app import app

        client = TestClient(app)
        t0 = time.time()
        res = client.get(
            "/api/v1/screener/run?preset=balanced&top_n=15&min_amount_cny=50000000&mode=eod",
            headers={"X-API-Key": "dev-investor-key"},
        )
        elapsed = time.time() - t0
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()["ok"])
        self.assertLess(elapsed, 5.0, f"eod screener too slow: {elapsed:.2f}s")

    def test_live_mode_fast_path_no_fabric_block(self) -> None:
        from fastapi.testclient import TestClient

        from gateway.api.app import app

        client = TestClient(app)
        t0 = time.time()
        res = client.get(
            "/api/v1/screener/run?preset=balanced&top_n=15&min_amount_cny=50000000&mode=live",
            headers={"X-API-Key": "dev-investor-key"},
        )
        elapsed = time.time() - t0
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertLess(elapsed, 8.0, f"live screener blocked too long: {elapsed:.2f}s")
        live_status = body["data"].get("live_status") or {}
        if not live_status.get("used"):
            self.assertIn(live_status.get("fallback"), ("eod_factors_only", None))


if __name__ == "__main__":
    unittest.main()
