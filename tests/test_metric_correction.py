"""Metric correction unit tests — DSR, PBO, Rank IC, calibration, performance."""

from __future__ import annotations

import unittest

from quant.validation.calibration import summarize_calibration
from quant.validation.overfitting import build_pbo_candidate_matrix, deflated_sharpe_ratio, probability_backtest_overfitting
from quant.validation.performance import cumulative_return, max_drawdown, sharpe_ratio, summarize_performance
from quant.validation.rank_ic import daily_rank_ic, summarize_rank_ic


class TestDSR(unittest.TestCase):
    def test_zero_alpha_low_probability(self) -> None:
        r = deflated_sharpe_ratio(0.0, n_trials=50, n_obs=252)
        self.assertEqual(r["status"], "OK")
        self.assertLess(r["dsr_probability"], 0.5)

    def test_positive_sharpe_higher_probability(self) -> None:
        low = deflated_sharpe_ratio(0.2, n_trials=50, n_obs=252)
        high = deflated_sharpe_ratio(2.0, n_trials=3, n_obs=252)
        self.assertGreater(high["dsr_probability"], low["dsr_probability"])

    def test_insufficient_sample(self) -> None:
        r = deflated_sharpe_ratio(1.0, n_trials=5, n_obs=5)
        self.assertEqual(r["status"], "INSUFFICIENT_SAMPLE")


class TestPBO(unittest.TestCase):
    def test_insufficient_strategies(self) -> None:
        r = probability_backtest_overfitting([[0.1, 0.2, 0.3]])
        self.assertEqual(r["status"], "INSUFFICIENT_SAMPLE")
        self.assertIsNone(r["pbo"])

    def test_candidate_matrix_meets_minimum(self) -> None:
        primary = [0.1 * (i % 3 - 1) for i in range(30)]
        matrix = build_pbo_candidate_matrix(primary, n_variants=12)
        self.assertGreaterEqual(len(matrix), 8)
        r = probability_backtest_overfitting(matrix)
        self.assertIn(r["status"], ("OK", "INSUFFICIENT_SAMPLE"))


class TestRankIC(unittest.TestCase):
    def test_perfect_positive_ic(self) -> None:
        scores = {f"S{i}": float(i) for i in range(10)}
        rets = {f"S{i}": float(i) for i in range(10)}
        ic = daily_rank_ic(scores, rets)
        self.assertIsNotNone(ic)
        self.assertAlmostEqual(ic, 1.0, places=2)

    def test_summarize_insufficient(self) -> None:
        s = summarize_rank_ic([0.1, None, None])
        self.assertEqual(s["status"], "INSUFFICIENT_SAMPLE")


class TestPerformance(unittest.TestCase):
    def test_net_cumulative(self) -> None:
        daily = [1.0, -0.5, 0.3]
        cum = cumulative_return(daily)
        self.assertGreater(cum, 0)

    def test_drawdown_negative(self) -> None:
        dd = max_drawdown([2.0, -3.0, -2.0])
        self.assertLess(dd, 0)

    def test_sharpe_positive_stable(self) -> None:
        daily = [0.1 + (i % 3) * 0.01 for i in range(50)]
        self.assertGreater(sharpe_ratio(daily), 0)


class TestCalibration(unittest.TestCase):
    def test_insufficient_sample(self) -> None:
        r = summarize_calibration([0.5, 0.6], [1, 0])
        self.assertEqual(r["status"], "INSUFFICIENT_SAMPLE")


if __name__ == "__main__":
    unittest.main()
