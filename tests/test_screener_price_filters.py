"""Screener price filters and selection guide."""

from __future__ import annotations

import unittest

from quant.screener.selection_guide import build_selection_guide, price_passes, resolve_price_filters


class TestPriceFilters(unittest.TestCase):
    def test_capital_ceiling(self):
        pmin, user_max, eff_max, cap = resolve_price_filters(
            price_min_cny=0,
            price_max_cny=None,
            capital_cny=5000,
            enforce_capital_price_ceiling=True,
        )
        self.assertEqual(cap, 5000.0)
        self.assertEqual(eff_max, 50.0)
        self.assertTrue(price_passes(49.0, pmin=pmin, eff_max=eff_max))
        self.assertFalse(price_passes(51.0, pmin=pmin, eff_max=eff_max))

    def test_min_max_range(self):
        pmin, user_max, eff_max, _ = resolve_price_filters(
            price_min_cny=10,
            price_max_cny=30,
            capital_cny=100000,
            enforce_capital_price_ceiling=False,
        )
        self.assertEqual(pmin, 10.0)
        self.assertEqual(eff_max, 30.0)
        self.assertFalse(price_passes(9.0, pmin=pmin, eff_max=eff_max))
        self.assertTrue(price_passes(20.0, pmin=pmin, eff_max=eff_max))

    def test_selection_guide_includes_price_summary(self):
        guide = build_selection_guide(
            preset="balanced",
            mode="eod",
            capital_cny=5000,
            price_min_cny=5,
            price_max_cny=40,
            enforce_capital_price_ceiling=True,
            universe_size=100,
            candidate_count=10,
            validation_status="NOT_READY",
            as_of_date="2026-06-17",
        )
        self.assertEqual(guide["title"], "增强版选股指南")
        self.assertIn("最低价", guide["price_filter_summary"])
        self.assertIn("effective_price_max_cny", guide)
        self.assertLessEqual(guide["effective_price_max_cny"], 50.0)


if __name__ == "__main__":
    unittest.main()
