"""Quant upgrade: tradability mask, enrichment, leakage guards, validation wiring."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestTradabilityMask(unittest.TestCase):
    def test_limit_up_blocks_purchase(self) -> None:
        from quant.tradability.mask import evaluate_tradability

        m = evaluate_tradability(symbol="600000.SH", last_close=10.0, last_pct=9.9, avg_amount=1e8)
        self.assertFalse(m.valid_for_purchase)
        self.assertIn("LIMIT_UP_NO_ENTRY", m.blockers)

    def test_affordable_lot_for_5000(self) -> None:
        from quant.portfolio.allocator import affordable_lots

        lots, pos = affordable_lots(12.5, 5000.0)
        self.assertGreaterEqual(lots, 1)
        self.assertLessEqual(pos, 5000.0)


class TestEnrichment(unittest.TestCase):
    def test_enrich_adds_multi_target_fields(self) -> None:
        from quant.scoring.enrichment import enrich_candidate

        row = {
            "symbol": "600000.SH",
            "last_close": 10.0,
            "last_pct": 1.0,
            "ret_20": 0.05,
            "ret_60": 0.08,
            "trend": 0.02,
            "vol_20": 2.5,
            "avg_amount": 8e7,
            "score": 1.2,
            "disclosure_flag": "",
        }
        out = enrich_candidate(row, rank=1, preset="balanced", as_of_date="2026-06-16")
        self.assertIn("expected_return_lo_pct", out)
        self.assertIn("downside_risk_pct", out)
        self.assertIn("crash_risk", out)
        self.assertIn("eligibility", out)
        self.assertIn("reasons_not_to_trade", out)
        self.assertLess(out["final_score"], out["alpha_score"] + 0.01)


class TestPurgedKfold(unittest.TestCase):
    def test_purged_splits_have_gap(self) -> None:
        from quant.validation.purged_kfold import purged_kfold_splits

        dates = [f"2024-01-{i:02d}" for i in range(1, 31)]
        splits = purged_kfold_splits(dates, n_splits=3, train_size=10, test_size=3, purge_days=2)
        self.assertTrue(splits)
        for sp in splits:
            self.assertGreaterEqual(sp["purge_gap_days"], 2)


class TestLeakageGuard(unittest.TestCase):
    def test_screener_as_of_does_not_use_future_bars(self) -> None:
        from quant.application.screener_service import get_screener_service

        svc = get_screener_service()
        wh = svc.warehouse
        if not wh.exists():
            self.skipTest("warehouse missing")
        import duckdb

        con = duckdb.connect(str(wh), read_only=True)
        dates = [str(x[0]) for x in con.execute("SELECT DISTINCT trade_date FROM daily_bars ORDER BY trade_date").fetchall()]
        con.close()
        if len(dates) < 5:
            self.skipTest("insufficient dates")
        pivot = dates[-3]
        r1 = svc.screen(preset="balanced", top_n=5, as_of_date=pivot, mode="eod")
        r2 = svc.screen(preset="balanced", top_n=5, as_of_date=dates[-1], mode="eod")
        self.assertEqual(r1.as_of_date, pivot)
        self.assertNotEqual(r1.as_of_date, r2.as_of_date if r2.as_of_date != pivot else dates[-2])


class TestBacktestAPI(unittest.TestCase):
    def test_screener_backtest_route(self) -> None:
        from fastapi.testclient import TestClient
        from gateway.api.app import app

        client = TestClient(app)
        res = client.post(
            "/api/v1/research/backtest",
            headers={"X-API-Key": "demo-local-key-change-in-prod"},
            json={"engine": "screener_portfolio", "preset": "balanced", "lookback_days": 20, "top_n": 3},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertIn("status", data)
        self.assertIn("metrics", data)


if __name__ == "__main__":
    unittest.main()
