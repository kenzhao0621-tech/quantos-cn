"""Phase 2 FeatureOS tests — version unification, market regime, naming honesty."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestVersionUnification(unittest.TestCase):
    def test_single_source_of_truth(self):
        from quant.version import SCREENER_ENGINE, SCREENER_MODEL_VERSION

        self.assertTrue(SCREENER_MODEL_VERSION.startswith("screener_v"))
        self.assertTrue(SCREENER_ENGINE.startswith("screener_v"))

    def test_no_legacy_version_strings_in_runtime_code(self):
        """Legacy v4/v5/v6 strings must not remain in runtime modules."""
        legacy = (
            "screener_v4_industry_neutral_2026-06-17",
            "screener_v5_ensemble_lgbm_2026-06-17",
            "screener_v6_trading_agents_zh",
        )
        runtime_files = [
            ROOT / "quant" / "application" / "screener_service.py",
            ROOT / "quant" / "scoring" / "enrichment.py",
            ROOT / "gateway" / "api" / "app.py",
            ROOT / "gateway" / "api" / "bff_market.py",
            ROOT / "gateway" / "trading_pipeline.py",
        ]
        for f in runtime_files:
            text = f.read_text(encoding="utf-8")
            for s in legacy:
                self.assertNotIn(s, text, f"{f.name} still contains {s}")

    def test_enrichment_uses_shared_version(self):
        from quant.scoring.enrichment import MODEL_VERSION
        from quant.version import SCREENER_MODEL_VERSION

        self.assertEqual(MODEL_VERSION, SCREENER_MODEL_VERSION)


class TestNamingHonesty(unittest.TestCase):
    def test_price_momentum_lite_is_primary_name(self):
        from quant.screener.alpha_blend import price_momentum_lite_zscore, alpha158_lite_zscore

        row = {"symbol": "600000.SH"}
        z = {"ret_20": {"600000.SH": 1.0}, "ret_60": {"600000.SH": 0.5},
             "trend": {"600000.SH": 0.2}, "vol_20": {"600000.SH": -0.1},
             "avg_amount": {"600000.SH": 0.3}}
        self.assertEqual(price_momentum_lite_zscore(row, z), alpha158_lite_zscore(row, z))


class TestMarketRegime(unittest.TestCase):
    def test_regime_structure(self):
        from quant.features.market_regime import compute_market_regime

        r = compute_market_regime()
        self.assertIn("regime", r)
        self.assertIn("score", r)
        self.assertIn("degraded", r)
        self.assertGreaterEqual(r["score"], -1.0)
        self.assertLessEqual(r["score"], 1.0)
        if not r["degraded"]:
            self.assertIn(r["regime"], ("BULL_TREND", "MILD_UP", "RANGE_BOUND", "MILD_DOWN", "BEAR_TREND"))
            self.assertGreaterEqual(r["bars_used"], 40)

    def test_degraded_on_missing_index(self):
        from quant.features.market_regime import compute_market_regime

        r = compute_market_regime(index_code="999999.XX")
        self.assertTrue(r["degraded"])
        self.assertEqual(r["regime"], "UNKNOWN")


class TestLookaheadGate(unittest.TestCase):
    def test_leakage_audit_runs_and_passes(self):
        from quant.validation.leakage_detector import run_leakage_audit

        report = run_leakage_audit()
        self.assertTrue(report["passed"], [c for c in report["checks"] if not c["passed"]])


if __name__ == "__main__":
    unittest.main()
