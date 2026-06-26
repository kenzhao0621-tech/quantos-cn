"""Stock search and single-symbol analyze API."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from gateway.api.app import app
from quant.application.screener_service import get_screener_service
from quant.screener.symbol_search import normalize_symbol_input, search_symbols


class TestSymbolSearch(unittest.TestCase):
    def test_normalize_symbol_input(self) -> None:
        self.assertEqual(normalize_symbol_input("600519"), "600519.SH")
        self.assertEqual(normalize_symbol_input("000001.SZ"), "000001.SZ")
        self.assertEqual(normalize_symbol_input("  600519.sh  "), "600519.SH")

    def test_search_by_code_fragment(self) -> None:
        hits = search_symbols("600519", limit=5)
        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["symbol"], "600519.SH")

    def test_search_by_name(self) -> None:
        hits = search_symbols("平安", limit=5)
        self.assertGreater(len(hits), 0)
        self.assertTrue(any("平安" in h.get("name", "") for h in hits))

    def test_analyze_symbol_returns_score(self) -> None:
        svc = get_screener_service()
        result = svc.analyze_symbol("600519", preset="balanced", mode="eod")
        if result.get("blocked"):
            self.skipTest(result.get("blocker_reason", "blocked"))
        self.assertEqual(result["symbol"], "600519.SH")
        self.assertTrue(result.get("name"))
        self.assertIsNotNone(result.get("score"))
        self.assertGreater(result.get("rank", 0), 0)
        self.assertTrue(result.get("detailed_reasons"))

    def test_search_api(self) -> None:
        client = TestClient(app)
        res = client.get(
            "/api/v1/screener/search",
            params={"q": "茅台", "limit": 5},
            headers={"X-API-Key": "dev-investor-key"},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body.get("ok"))
        self.assertGreater(body["data"]["count"], 0)

    def test_analyze_api(self) -> None:
        client = TestClient(app)
        res = client.get(
            "/api/v1/screener/analyze/600519.SH",
            params={"preset": "balanced", "mode": "eod"},
            headers={"X-API-Key": "dev-investor-key"},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        if not body.get("ok"):
            self.skipTest(body.get("error", {}).get("message", "blocked"))
        data = body["data"]
        self.assertEqual(data["symbol"], "600519.SH")
        self.assertIn("score", data)
        self.assertIn("detailed_reasons", data)
        self.assertIn("percentile_top", data)


if __name__ == "__main__":
    unittest.main()
