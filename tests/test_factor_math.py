"""Factor math unit tests."""

from __future__ import annotations

import unittest

from quant.features.factor_library import compute_fundamental_factors, compute_price_factors, risk_event_score
from quant.features.preprocess import robust_zscore, winsorize


class TestFactorMath(unittest.TestCase):
    def test_winsorize_clips_extremes(self) -> None:
        vals = [float(i) for i in range(100)] + [1000.0]
        out = winsorize(vals, lower=0.01, upper=0.99)
        self.assertLess(max(out), 1000.0)

    def test_price_factors_ret20(self) -> None:
        closes = [10.0 + i * 0.1 for i in range(25)]
        f = compute_price_factors(closes)
        self.assertIn("ret_20", f)
        self.assertIsNotNone(f["ret_20"])

    def test_pe_non_positive_is_nan(self) -> None:
        f = compute_fundamental_factors({"pe": -1, "pb": 2})
        self.assertIsNone(f["value_pe"])

    def test_risk_event_severity(self) -> None:
        self.assertEqual(risk_event_score("HIGH"), -2.0)
        self.assertEqual(risk_event_score("LOW"), -0.3)


if __name__ == "__main__":
    unittest.main()
