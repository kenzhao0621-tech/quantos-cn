"""Phase 1 DataOS regression tests — ST flags, board limits, freshness honesty."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestTushareDailyAdapter(unittest.TestCase):
    def _normalize(self, rows):
        from quant.providers.tushare_daily_adapter import normalize_tushare_daily

        return normalize_tushare_daily(rows, trade_date="20260626")

    def test_board_classification(self):
        payload = self._normalize([
            {"ts_code": "600000.SH", "close": 10.0, "pct_chg": 0.0, "vol": 1},
            {"ts_code": "688001.SH", "close": 10.0, "pct_chg": 0.0, "vol": 1},
            {"ts_code": "300750.SZ", "close": 10.0, "pct_chg": 0.0, "vol": 1},
            {"ts_code": "830001.BJ", "close": 10.0, "pct_chg": 0.0, "vol": 1},
        ])
        boards = {r["ts_code"]: r["board"] for r in payload["rows"]}
        self.assertEqual(boards["600000.SH"], "MAIN_SH")
        self.assertEqual(boards["688001.SH"], "STAR")
        self.assertEqual(boards["300750.SZ"], "CHINEXT")
        self.assertEqual(boards["830001.BJ"], "BSE")

    def test_limit_pct_per_board(self):
        payload = self._normalize([
            {"ts_code": "600000.SH", "close": 10.0, "pct_chg": 9.9, "vol": 1},
            {"ts_code": "688001.SH", "close": 10.0, "pct_chg": 9.9, "vol": 1},
        ])
        by = {r["ts_code"]: r for r in payload["rows"]}
        self.assertTrue(by["600000.SH"]["at_limit_up"])   # main board 10%
        self.assertFalse(by["688001.SH"]["at_limit_up"])  # STAR 20%
        self.assertEqual(by["688001.SH"]["limit_pct"], 20.0)

    def test_is_st_never_hardcoded_false(self):
        """is_st must be True/False from security master or None (unknown) — not fake False."""
        payload = self._normalize([{"ts_code": "999999.SH", "close": 1.0, "pct_chg": 0.0, "vol": 1}])
        row = payload["rows"][0]
        # Unknown symbol has no name — flag must be None, not False.
        self.assertIsNone(row["is_st"])
        self.assertIn(payload["st_flag_source"], ("security_master_name", "unavailable"))

    def test_paused_flag_from_zero_volume(self):
        payload = self._normalize([
            {"ts_code": "600000.SH", "close": 10.0, "pct_chg": 0.0, "vol": 0},
            {"ts_code": "600001.SH", "close": 10.0, "pct_chg": 0.0, "vol": 100},
        ])
        by = {r["ts_code"]: r for r in payload["rows"]}
        self.assertTrue(by["600000.SH"]["paused"])
        self.assertFalse(by["600001.SH"]["paused"])


class TestBoardLimits(unittest.TestCase):
    def test_board_limit_pct(self):
        from quant.tradability.mask import board_limit_pct

        self.assertEqual(board_limit_pct("600000.SH"), 10.0)
        self.assertEqual(board_limit_pct("600000.SH", is_st=True), 5.0)
        self.assertEqual(board_limit_pct("688001.SH"), 20.0)
        self.assertEqual(board_limit_pct("300750.SZ"), 20.0)
        self.assertEqual(board_limit_pct("830001.BJ"), 30.0)

    def test_star_board_not_blocked_at_ten_pct(self):
        from quant.tradability.mask import evaluate_tradability

        mask = evaluate_tradability(
            symbol="688001.SH", last_close=30.0, last_pct=10.5,
            avg_amount=1e8, capital_cny=1e5,
        )
        self.assertNotIn("LIMIT_UP_NO_ENTRY", mask.blockers)

    def test_main_board_blocked_near_limit(self):
        from quant.tradability.mask import evaluate_tradability

        mask = evaluate_tradability(
            symbol="600000.SH", last_close=10.0, last_pct=9.9,
            avg_amount=1e8, capital_cny=1e5,
        )
        self.assertIn("LIMIT_UP_NO_ENTRY", mask.blockers)


class TestMarketStatusHonesty(unittest.TestCase):
    """stale_fallback snapshots must never be reported live-OK (DATA_SOURCE_AUDIT §6)."""

    def _status_with_snapshot(self, snapshot: dict) -> dict:
        import gateway.market_status as ms

        tmp = ROOT / "data" / "gateway" / "test_live_snapshot_phase1.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(snapshot), encoding="utf-8")
        original = ms.LIVE_SNAPSHOT
        ms.LIVE_SNAPSHOT = tmp
        try:
            return ms._live_status()
        finally:
            ms.LIVE_SNAPSHOT = original
            tmp.unlink(missing_ok=True)

    def _rows(self, n=150):
        return [{"code": f"{i:06d}", "price": 10.0} for i in range(n)]

    def test_stale_fallback_not_ok(self):
        from datetime import datetime

        status = self._status_with_snapshot({
            "success": True,
            "stale_fallback": True,
            "retrieved_at": datetime.now().isoformat(timespec="seconds"),
            "rows": self._rows(),
        })
        self.assertFalse(status["ok"])
        self.assertTrue(status["stale"])

    def test_old_snapshot_not_ok(self):
        status = self._status_with_snapshot({
            "success": True,
            "retrieved_at": "2026-01-01T09:30:00",
            "rows": self._rows(),
        })
        self.assertFalse(status["ok"])
        self.assertTrue(status["stale"])

    def test_fresh_snapshot_ok(self):
        from datetime import datetime

        status = self._status_with_snapshot({
            "success": True,
            "retrieved_at": datetime.now().isoformat(timespec="seconds"),
            "rows": self._rows(),
        })
        self.assertTrue(status["ok"])
        self.assertFalse(status["stale"])


class TestWarehouseViews(unittest.TestCase):
    def test_new_views_registered(self):
        wh = ROOT / "data" / "warehouse" / "quant.duckdb"
        if not wh.exists():
            self.skipTest("warehouse not present in this environment")
        import duckdb

        con = duckdb.connect(str(wh), read_only=True)
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        con.close()
        for view in ("industry_map", "fundamental", "adj_factors", "daily_bars_adj"):
            self.assertIn(view, tables)


if __name__ == "__main__":
    unittest.main()
