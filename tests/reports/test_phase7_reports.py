"""Phase 7 ReportOS tests — report generation honesty."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestMarkdownReport(unittest.TestCase):
    def test_report_generates_and_has_disclaimer(self):
        from quant.reports.markdown_report import generate_research_report

        path = generate_research_report()
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("不构成投资建议", text)
        self.assertIn("真实性与降级状态汇总", text)
        for banned in ("保证收益", "稳赚", "必涨", "无风险", "100%胜率"):
            self.assertNotIn(banned, text)
        path.unlink(missing_ok=True)

    def test_missing_artifacts_reported_not_faked(self):
        import tempfile

        from quant.reports import markdown_report

        # Point the module at an empty root so every artifact is missing.
        original = markdown_report.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            markdown_report.ROOT = Path(tmp)
            try:
                path = markdown_report.generate_research_report(out_dir=Path(tmp) / "out")
                text = path.read_text(encoding="utf-8")
                self.assertGreaterEqual(text.count("NOT_RUN"), 4)
                self.assertIn("degraded/缺失", text)
            finally:
                markdown_report.ROOT = original


class TestFrontendWiring(unittest.TestCase):
    def test_no_hardcoded_backtest_date(self):
        src = (ROOT / "apps" / "portal-web" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn('"2026-06-16"', src)

    def test_reports_and_risk_tabs_restored(self):
        html = (ROOT / "apps" / "portal-web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="reports"', html.split("<main")[0])
        self.assertIn('data-page="risk"', html.split("<main")[0])

    def test_agents_analyze_ui_present(self):
        html = (ROOT / "apps" / "portal-web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-action="agents-analyze"', html)
        ui = (ROOT / "apps" / "portal-web" / "ui-render.js").read_text(encoding="utf-8")
        self.assertIn("renderAgentsAnalysis", ui)
        self.assertIn("renderBacktestReport", ui)

    def test_curve_chart_capability(self):
        ui = (ROOT / "apps" / "portal-web" / "ui-render.js").read_text(encoding="utf-8")
        self.assertIn("curveChartSvg", ui)


if __name__ == "__main__":
    unittest.main()
