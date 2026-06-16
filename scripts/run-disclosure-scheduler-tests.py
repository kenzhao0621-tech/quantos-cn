#!/usr/bin/env python3
"""Disclosure, scheduler, PDF, and candidate-gate deterministic tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "ai" / "daily-trading"


class TestDisclosureNormalization(unittest.TestCase):
    def test_cninfo_normalize(self) -> None:
        from quant.disclosures.models import normalize_cninfo_row, classify_category
        row = normalize_cninfo_row({
            "secCode": "600000", "secName": "浦发银行",
            "announcementTitle": "关于停牌的公告", "announcementTime": "2026-06-15 10:00:00",
        }, provider="cninfo_official")
        self.assertEqual(row["exchange"], "SSE")
        self.assertEqual(row["category"], "SUSPENSION")
        cat, _, _ = classify_category("2025年年度报告")
        self.assertEqual(cat, "PERIODIC_REPORT")


class TestPITFilter(unittest.TestCase):
    def test_future_rejected(self) -> None:
        from quant.disclosures.pit_filter import filter_point_in_time
        rows = [{"disclosure_id": "1", "official_publication_time": "2026-06-20 10:00:00"}]
        r = filter_point_in_time(rows, analysis_cutoff="2026-06-16")
        self.assertEqual(len(r.rejected), 1)
        self.assertEqual(len(r.passed), 0)

    def test_past_passes(self) -> None:
        from quant.disclosures.pit_filter import filter_point_in_time
        rows = [{"disclosure_id": "2", "official_publication_time": "2026-06-10 10:00:00"}]
        r = filter_point_in_time(rows, analysis_cutoff="2026-06-16")
        self.assertEqual(len(r.passed), 1)


class TestCandidateGateDisclosure(unittest.TestCase):
    def test_verified_zero_passes(self) -> None:
        from quant.disclosures.candidate_gate import evaluate_disclosure_readiness
        r = evaluate_disclosure_readiness({
            "query_state": "DISCLOSURE_QUERY_COMPLETE_ZERO_RESULTS",
            "primary_status": "SUCCESS_ZERO_RESULTS",
            "primary_provider": "cninfo_official",
            "row_count": 0,
            "verified_zero_results": True,
        })
        self.assertTrue(r.passed)
        self.assertEqual(r.state, "PASS_WITH_VERIFIED_ZERO_RESULTS")

    def test_unavailable_blocks(self) -> None:
        from quant.disclosures.candidate_gate import evaluate_disclosure_readiness
        r = evaluate_disclosure_readiness({
            "query_state": "DISCLOSURE_DATA_UNAVAILABLE",
            "primary_status": "NETWORK_UNAVAILABLE",
            "row_count": 0,
        })
        self.assertFalse(r.passed)
        self.assertEqual(r.state, "BLOCKED_PROVIDER_UNAVAILABLE")


class TestLocalProvider(unittest.TestCase):
    def test_fixture_rows(self) -> None:
        from quant.disclosures.providers.local_snapshot import LocalDisclosureSnapshotProvider
        p = LocalDisclosureSnapshotProvider()
        end = datetime.now()
        start = end - timedelta(days=30)
        r = p.fetch_announcements(start, end)
        self.assertTrue(r.query_completed)
        self.assertGreater(r.row_count, 0)


class TestSchedulerDateSelection(unittest.TestCase):
    def test_next_open_forward(self) -> None:
        from quant.live_test_scheduler import _next_open_session_at_0940
        from zoneinfo import ZoneInfo
        target = _next_open_session_at_0940()
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        self.assertGreater(target, now.replace(tzinfo=None) if target.tzinfo is None else now)

    def test_trading_day_fn(self) -> None:
        from quant.daily_report_scheduler import is_trading_day_today
        # Should not raise
        is_trading_day_today()


class TestPDFRenderer(unittest.TestCase):
    def test_html_and_qa(self) -> None:
        from quant.report_renderer import render_html, qa_pdf, render_all_formats
        report = {
            "run_id": "test123", "data_cutoff": "2026-06-16", "decision": "NO_TRADE",
            "provider": "akshare_sina", "freshness": "END_OF_DAY", "spot_row_count": 5500,
            "regime": "neutral", "regime_confidence": "MEDIUM", "no_trade_reasons": ["test"],
            "sections": {"disclosures": {"disclosure_readiness": {"state": "PASS_WITH_VERIFIED_ZERO_RESULTS"}}},
        }
        html = render_html(report)
        self.assertIn("中国A股", html)
        with tempfile.TemporaryDirectory() as td:
            paths = render_all_formats(report, base_name="test_report")
            pdf = paths.get("pdf")
            if pdf and Path(pdf).exists():
                qa = qa_pdf(Path(pdf), report, min_bytes=100)
                self.assertTrue(qa["checks"][0]["passed"])


class TestSecurityRedaction(unittest.TestCase):
    def test_header_redaction(self) -> None:
        from quant.disclosures.raw_store import _redact_headers
        h = _redact_headers({"Authorization": "Bearer secret", "Content-Type": "json"})
        self.assertEqual(h["Authorization"], "[REDACTED]")
        self.assertEqual(h["Content-Type"], "json")


class TestFailureInjection(unittest.TestCase):
    def test_network_unavailable(self) -> None:
        from quant.disclosures.providers.cninfo import CNInfoOfficialProvider
        from quant.disclosures.protocol import DisclosureStatus
        p = CNInfoOfficialProvider()
        with patch("urllib.request.urlopen", side_effect=OSError("network down")):
            r = p.fetch_announcements(datetime.now() - timedelta(days=7), datetime.now())
        self.assertEqual(r.status, DisclosureStatus.NETWORK_UNAVAILABLE)
        self.assertFalse(r.query_completed)


def main() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestDisclosureNormalization, TestPITFilter, TestCandidateGateDisclosure,
        TestLocalProvider, TestSchedulerDateSelection, TestPDFRenderer,
        TestSecurityRedaction, TestFailureInjection,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "passed": result.wasSuccessful(),
        "run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "DISCLOSURE_SCHEDULER_TEST_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
