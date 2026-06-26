"""Screener must return Chinese stock names and Alpha158 blend scores."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from gateway.api.app import app
from quant.application.screener_service import get_screener_service
from quant.screener.names import resolve_name


class TestScreenerNamesAndAlgo(unittest.TestCase):
    def test_resolve_name_known_symbol(self) -> None:
        name = resolve_name("000001.SZ")
        self.assertTrue(name)
        self.assertIn("平安", name)

    def test_screen_returns_names(self) -> None:
        svc = get_screener_service()
        result = svc.screen(preset="balanced", top_n=10, mode="eod")
        if result.blocked:
            self.skipTest(result.blocker_reason or "warehouse blocked")
        self.assertGreater(len(result.candidates), 0)
        with_names = [c for c in result.candidates if c.name]
        self.assertGreaterEqual(len(with_names), max(1, len(result.candidates) // 2))
        enriched = result.to_dict()
        top = enriched["candidates"][0]
        self.assertTrue(top.get("name"), "top candidate should have name")
        self.assertIn("detailed_reasons", top)
        self.assertIn("trade_zones", top)
        self.assertIn("alpha158_inspired_lite", top.get("factor_contributions", {}))

    def test_screener_api_includes_name(self) -> None:
        client = TestClient(app)
        res = client.get(
            "/api/v1/screener/run",
            params={"preset": "balanced", "top_n": 8, "mode": "eod"},
            headers={"X-API-Key": "dev-investor-key"},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        if not body.get("ok"):
            self.skipTest(body.get("error", {}).get("message", "blocked"))
        cands = body["data"]["candidates"]
        self.assertGreater(len(cands), 0)
        self.assertTrue(cands[0].get("name"))
        self.assertEqual(body["data"]["model_version"], "screener_v4_industry_neutral_2026-06-17")

    def test_dossier_includes_trade_zones(self) -> None:
        svc = get_screener_service()
        screen = svc.screen(top_n=5, mode="eod")
        if screen.blocked or not screen.candidates:
            self.skipTest("no candidates")
        sym = screen.candidates[0].symbol
        dossier = svc.dossier(sym, mode="eod")
        self.assertEqual(dossier["symbol"], sym)
        self.assertTrue(dossier.get("name"))
        self.assertIn("trade_zones", dossier)
        self.assertTrue(dossier["trade_zones"].get("buy_zone_low"))


if __name__ == "__main__":
    unittest.main()
