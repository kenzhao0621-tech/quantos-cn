"""Tests for unified operations ledger and trading ops reports."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class OperationsLedgerTests(unittest.TestCase):
    def test_append_and_summarize(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "operations_ledger.jsonl"
            with mock.patch("gateway.brokers.operations_ledger.LEDGER_PATH", ledger):
                from gateway.brokers.operations_ledger import append_operation, list_operations, summarize_day

                append_operation(mode="paper", action="screener_favorite", symbol="600519.SH", name="贵州茅台")
                append_operation(mode="real", action="watchlist_sync", details={"synced": ["600519.SH"]})
                rows = list_operations(mode="paper")
                self.assertEqual(len(rows), 1)
                summary = summarize_day()
                self.assertIn("paper", summary)
                self.assertIn("real", summary)
                self.assertEqual(summary["paper"]["operation_count"], 1)
                self.assertEqual(summary["real"]["operation_count"], 1)


class TradingOpsReportTests(unittest.TestCase):
    def test_generate_trading_ops_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            daily = Path(tmp) / "daily"
            daily.mkdir(parents=True)
            ledger = Path(tmp) / "operations_ledger.jsonl"
            ledger.write_text(
                json.dumps({
                    "ts": "2026-06-17T08:00:00+00:00",
                    "trade_date": "2026-06-17",
                    "session": "intraday",
                    "mode": "paper",
                    "action": "screener_favorite",
                    "symbol": "601398.SH",
                    "status": "ok",
                    "details": {},
                }) + "\n",
                encoding="utf-8",
            )
            with mock.patch("gateway.brokers.operations_ledger.LEDGER_PATH", ledger), \
                 mock.patch("quant.trading_ops_report.DAILY_DIR", daily), \
                 mock.patch("quant.trading_report_renderer.DESKTOP_ROOT", Path(tmp) / "desktop"):
                from quant.trading_ops_report import generate_trading_ops_reports

                paths = generate_trading_ops_reports("2026-06-17", session="intraday")
                self.assertIn("modes", paths)
                self.assertTrue(Path(paths["modes"]["paper"]["json"]).exists())
                self.assertTrue(Path(paths["modes"]["paper"]["html"]).exists())


if __name__ == "__main__":
    unittest.main()
