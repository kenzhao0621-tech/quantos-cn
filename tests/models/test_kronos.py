"""KronosOS tests — contract, degraded path (network-free), signal normalization."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _fake_bars(n=120, start=10.0, drift=0.001):
    bars = []
    price = start
    for i in range(n):
        price *= 1 + drift + (0.01 if i % 7 == 0 else -0.004)
        bars.append({
            "timestamp": f"2026-{(i // 28) % 12 + 1:02d}-{i % 28 + 1:02d}",
            "open": price * 0.995, "high": price * 1.01, "low": price * 0.99,
            "close": price, "volume": 1000.0, "amount": 1000.0 * price,
        })
    return bars


class TestKronosDegradedPath(unittest.TestCase):
    """These tests never require the sidecar/model — degradation must be honest."""

    def _provider(self):
        from quant.models.kronos import KronosSignalProvider

        p = KronosSignalProvider(n_paths=20)
        # Force the degraded path regardless of local sidecar presence.
        p._call_sidecar = lambda bars, horizon: {"ok": False, "error": "forced_test_degrade"}
        return p

    def test_insufficient_history_is_degraded(self):
        p = self._provider()
        pred = p.predict_distribution("600000.SH", lookback_df=_fake_bars(5), horizon=5)
        self.assertTrue(pred["degraded"])
        self.assertIn("insufficient_history", pred["reason"])
        self.assertEqual(pred["paths"], [])

    def test_fallback_is_labeled_degraded(self):
        p = self._provider()
        pred = p.predict_distribution("600000.SH", lookback_df=_fake_bars(120), horizon=5)
        self.assertTrue(pred["degraded"])
        self.assertIn("bootstrap_mc_fallback", pred["reason"])
        self.assertEqual(len(pred["paths"]), 20)
        self.assertEqual(len(pred["paths"][0]), 5)

    def test_fallback_confidence_capped(self):
        """Statistical fallback must never claim model-grade confidence."""
        p = self._provider()
        pred = p.predict_distribution("600000.SH", lookback_df=_fake_bars(120), horizon=5)
        self.assertLessEqual(pred["confidence"], 0.35)

    def test_distribution_contract_fields(self):
        p = self._provider()
        pred = p.predict_distribution("600000.SH", lookback_df=_fake_bars(120), horizon=5)
        for key in ("symbol", "horizon", "paths", "expected_return", "volatility",
                    "downside_risk", "confidence", "model", "degraded", "reason"):
            self.assertIn(key, pred)

    def test_signal_contract_and_range(self):
        p = self._provider()
        pred = p.predict_distribution("600000.SH", lookback_df=_fake_bars(120), horizon=5)
        sig = p.generate_signal(pred)
        for key in ("symbol", "score", "rank_score", "confidence", "risk_penalty", "explanation", "degraded"):
            self.assertIn(key, sig)
        self.assertGreaterEqual(sig["score"], -1.0)
        self.assertLessEqual(sig["score"], 1.0)
        self.assertGreaterEqual(sig["confidence"], 0.0)
        self.assertLessEqual(sig["confidence"], 1.0)

    def test_no_profit_promises_in_explanation(self):
        p = self._provider()
        pred = p.predict_distribution("600000.SH", lookback_df=_fake_bars(120), horizon=5)
        sig = p.generate_signal(pred)
        for banned in ("保证收益", "稳赚", "必涨", "无风险", "100%胜率"):
            self.assertNotIn(banned, sig["explanation"])
        self.assertIn("不构成投资建议", sig["explanation"])

    def test_degraded_explanation_says_not_model(self):
        p = self._provider()
        pred = p.predict_distribution("600000.SH", lookback_df=_fake_bars(120), horizon=5)
        sig = p.generate_signal(pred)
        self.assertIn("降级", sig["explanation"])

    def test_fit_is_noop(self):
        p = self._provider()
        self.assertIsNone(p.fit(None))


class TestSidecarProtocolFiles(unittest.TestCase):
    def test_sidecar_script_exists(self):
        from quant.models.kronos.config import SIDECAR_SCRIPT

        self.assertTrue(SIDECAR_SCRIPT.exists())

    def test_availability_probe_returns_tuple(self):
        from quant.models.kronos.config import sidecar_available

        ok, reason = sidecar_available()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(reason, str)


if __name__ == "__main__":
    unittest.main()
