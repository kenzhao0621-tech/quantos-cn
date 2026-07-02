"""Phase 4 ValidationOS tests — real benchmarks, full metrics, validation gate."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestFullMetrics(unittest.TestCase):
    RETS = [0.5, -0.3, 0.8, -0.2, 0.4, -0.6, 0.9, 0.1, -0.4, 0.3] * 5

    def test_full_metric_block_structure(self):
        from quant.validation.performance import full_metrics

        m = full_metrics(self.RETS, label="test")
        self.assertEqual(m["status"], "OK")
        for section, keys in {
            "return": ("cumulative_return_pct", "annualized_return_pct", "win_rate_pct",
                       "profit_factor", "average_gain_pct", "average_loss_pct"),
            "risk": ("max_drawdown_pct", "annualized_volatility_pct", "sharpe", "sortino",
                     "calmar", "downside_deviation_pct", "tail_loss_95_pct", "worst_day_pct"),
        }.items():
            for k in keys:
                self.assertIn(k, m[section], f"{section}.{k} missing")
        self.assertIn("bootstrap_ci_mean_daily_pct", m["robustness"])

    def test_tail_loss_is_negative_quantile(self):
        from quant.validation.performance import tail_loss_95

        self.assertLess(tail_loss_95(self.RETS), 0)

    def test_insufficient_sample(self):
        from quant.validation.performance import full_metrics

        self.assertEqual(full_metrics([])["status"], "INSUFFICIENT_SAMPLE")


class TestValidationGate(unittest.TestCase):
    def _metrics(self, sharpe=1.2, mdd=-5.0, ann=20.0, days=60):
        return {
            "n_days": days,
            "return": {"annualized_return_pct": ann, "cumulative_return_pct": ann},
            "risk": {"sharpe": sharpe, "max_drawdown_pct": mdd},
        }

    def test_pass_path(self):
        from quant.validation.gate import evaluate_validation_gate

        g = evaluate_validation_gate(
            metrics=self._metrics(), benchmark_return_pct=5.0,
            costs_included=True, a_share_constraints_applied=True,
        )
        self.assertTrue(g["passed"])
        self.assertEqual(g["verdict"], "CANDIDATE_POOL_ELIGIBLE")

    def test_blocked_without_costs(self):
        from quant.validation.gate import evaluate_validation_gate

        g = evaluate_validation_gate(
            metrics=self._metrics(), benchmark_return_pct=5.0,
            costs_included=False, a_share_constraints_applied=True,
        )
        self.assertFalse(g["passed"])
        self.assertEqual(g["verdict"], "BLOCKED_BY_VALIDATION")

    def test_blocked_without_benchmark(self):
        from quant.validation.gate import evaluate_validation_gate

        g = evaluate_validation_gate(
            metrics=self._metrics(), benchmark_return_pct=None,
            costs_included=True, a_share_constraints_applied=True,
        )
        self.assertFalse(g["passed"])

    def test_blocked_when_underperforming_benchmark(self):
        from quant.validation.gate import evaluate_validation_gate

        g = evaluate_validation_gate(
            metrics=self._metrics(ann=3.0), benchmark_return_pct=5.0,
            costs_included=True, a_share_constraints_applied=True,
        )
        self.assertFalse(g["passed"])

    def test_blocked_on_insufficient_history(self):
        from quant.validation.gate import evaluate_validation_gate

        g = evaluate_validation_gate(
            metrics=self._metrics(days=10), benchmark_return_pct=5.0,
            costs_included=True, a_share_constraints_applied=True,
        )
        self.assertFalse(g["passed"])
        self.assertTrue(any("insufficient_history" in r for r in g["reasons"]))

    def test_gate_has_disclaimer(self):
        from quant.validation.gate import evaluate_validation_gate

        g = evaluate_validation_gate(
            metrics=self._metrics(), benchmark_return_pct=5.0,
            costs_included=True, a_share_constraints_applied=True,
        )
        self.assertIn("不构成投资建议", g["disclaimer"])


class TestRealBenchmarks(unittest.TestCase):
    def test_no_fake_benchmark_multipliers(self):
        """The fake `total_ret * 0.6` benchmarks must be gone."""
        src = (ROOT / "gateway" / "backtest" / "screener_backtest.py").read_text(encoding="utf-8")
        self.assertNotIn("total_ret * 0.6", src)
        self.assertNotIn("total_ret * 0.5", src)
        self.assertNotIn("total_ret * 0.4", src)

    def test_event_engine_no_hardcoded_returns(self):
        src = (ROOT / "gateway" / "backtest" / "event_engine.py").read_text(encoding="utf-8")
        self.assertNotIn("[0.01] * len(fills)", src)

    def test_real_benchmarks_from_warehouse(self):
        wh = ROOT / "data" / "warehouse" / "quant.duckdb"
        if not wh.exists():
            self.skipTest("warehouse not present")
        from gateway.backtest.screener_backtest import _real_benchmarks

        b = _real_benchmarks("2026-05-01", "2026-06-26")
        if b["degraded"]:
            self.skipTest(f"benchmark degraded in this env: {b['reason']}")
        self.assertIn("hs300_buy_hold", b["values"])
        self.assertEqual(b["sources"]["hs300_buy_hold"], "index_bars 000300.SH real closes")


class TestEventEngineRealReturns(unittest.TestCase):
    def test_returns_resolved_from_bars(self):
        from gateway.backtest.event_engine import run_event_backtest

        bars = [
            {"symbol": "600000.SH", "date": "2026-06-20", "close": 10.0},
            {"symbol": "600000.SH", "date": "2026-06-23", "close": 10.5},
        ]
        signals = [{"symbol": "600000.SH", "date": "2026-06-20", "side": "BUY", "price": 10.0}]
        res = run_event_backtest(
            run_id="t1", as_of_date="2026-06-23", bars=bars, signals=signals,
        )
        self.assertEqual(res.metrics.get("trades"), 1.0)
        self.assertAlmostEqual(res.metrics.get("mean_return"), 0.05, places=5)

    def test_no_exit_means_blocked_not_faked(self):
        from gateway.backtest.event_engine import run_event_backtest

        bars = [{"symbol": "600000.SH", "date": "2026-06-20", "close": 10.0}]
        signals = [{"symbol": "600000.SH", "date": "2026-06-20", "side": "BUY", "price": 10.0}]
        res = run_event_backtest(run_id="t2", as_of_date="2026-06-20", bars=bars, signals=signals)
        self.assertNotIn("sharpe", res.metrics)
        self.assertTrue(any("NO_RESOLVABLE_EXITS" in b for b in res.blockers))


if __name__ == "__main__":
    unittest.main()
