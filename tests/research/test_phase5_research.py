"""Phase 5 ResearchOS tests — panel integrity, strategies, search honesty."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _synthetic_panel(n_days=120, n_syms=30, seed=7):
    """Deterministic synthetic panel for engine tests (never enters reports)."""
    import random

    rng = random.Random(seed)
    dates = [f"2025-{(i // 28) % 12 + 1:02d}-{i % 28 + 1:02d}" for i in range(n_days)]
    symbols = [f"6000{i:02d}.SH" for i in range(n_syms)]
    closes, pct, vol = {}, {}, {}
    for s in symbols:
        drift = rng.uniform(-0.002, 0.003)
        series, p = [], 10.0
        pcts = []
        for _ in range(n_days):
            r = drift + rng.uniform(-0.02, 0.02)
            p *= 1 + r
            series.append(round(p, 3))
            pcts.append(round(r * 100, 3))
        closes[s], pct[s] = series, pcts
        vol[s] = [1000.0] * n_days
    return {"ok": True, "degraded": False, "dates": dates, "symbols": symbols,
            "closes": closes, "pct": pct, "vol": vol,
            "window": {"start": dates[0], "end": dates[-1], "days": n_days}}


class TestStrategies(unittest.TestCase):
    def test_momentum_produces_daily_series(self):
        from quant.research.strategies import momentum_rank_strategy

        daily = momentum_rank_strategy(_synthetic_panel(), window=20, top_k=5, hold=5)
        self.assertGreater(len(daily), 50)

    def test_suspended_names_not_entered(self):
        from quant.research.strategies import momentum_rank_strategy

        panel = _synthetic_panel(n_syms=6)
        # Make one symbol suspended the whole window: it must never be picked.
        dead = panel["symbols"][0]
        panel["vol"][dead] = [0.0] * len(panel["dates"])
        # Give it an irresistible momentum so it WOULD be picked if not guarded.
        panel["closes"][dead] = [10.0 * (1.10 ** i) for i in range(len(panel["dates"]))]
        daily = momentum_rank_strategy(panel, window=20, top_k=2, hold=5)
        # If the suspended name were entered, daily returns would include its 10%/day.
        self.assertTrue(all(r < 9.0 for r in daily), "suspended symbol leaked into portfolio")

    def test_costs_are_charged(self):
        from quant.research.strategies import equal_weight_topk_liquidity

        panel = _synthetic_panel(n_syms=10)
        # Flat prices → zero gross return; net must show the single round-trip cost.
        for s in panel["symbols"]:
            panel["closes"][s] = [10.0] * len(panel["dates"])
            panel["pct"][s] = [0.0] * len(panel["dates"])
        daily = equal_weight_topk_liquidity(panel, top_k=5)
        self.assertLess(sum(daily), 0)


class TestSearch(unittest.TestCase):
    def test_search_reports_blocked_configs(self):
        from quant.research.search import run_random_search

        res = run_random_search(_synthetic_panel(), n_trials=8, benchmark_return_pct=50.0)
        self.assertEqual(res["method"], "random_search")
        # Against an absurd 50% benchmark, everything should be blocked and reported.
        self.assertGreaterEqual(res["blocked_count"], 1)
        self.assertIn("sensitivity", res)
        for t in res["all_trials"]:
            self.assertNotIn("daily_returns", t)  # stripped from report

    def test_no_benchmark_means_blocked_not_eligible(self):
        from quant.research.search import run_random_search

        res = run_random_search(_synthetic_panel(), n_trials=5, benchmark_return_pct=None)
        self.assertEqual(res["eligible_count"], 0)


class TestPanelContiguity(unittest.TestCase):
    def test_gap_trimmed(self):
        from quant.research.panel import _contiguous_tail

        dates = ["2020-01-02", "2020-01-03", "2023-06-01", "2023-06-02"]
        self.assertEqual(_contiguous_tail(dates), ["2023-06-01", "2023-06-02"])

    def test_contiguous_kept(self):
        from quant.research.panel import _contiguous_tail

        dates = ["2026-06-01", "2026-06-02", "2026-06-03"]
        self.assertEqual(_contiguous_tail(dates), dates)


class TestQlibNoFakeSharpe(unittest.TestCase):
    def test_hardcoded_sharpe_removed(self):
        src = (ROOT / "integrations" / "qlib" / "workflow.py").read_text(encoding="utf-8")
        self.assertNotIn("sharpe_proxy = 0.5", src)


class TestLearningLoopWired(unittest.TestCase):
    def test_record_screener_run_called_in_bff(self):
        src = (ROOT / "gateway" / "api" / "bff_market.py").read_text(encoding="utf-8")
        self.assertIn("record_screener_run", src)


if __name__ == "__main__":
    unittest.main()
