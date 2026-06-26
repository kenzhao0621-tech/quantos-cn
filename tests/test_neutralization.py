"""Tests for industry/size neutralization."""

from __future__ import annotations

import math
import unittest

from quant.features.neutralization import (
    cross_section_zscores,
    industry_neutral_zscores,
    neutralize_size_industry,
)
from quant.features.preprocess import cross_section_z, winsorize


class TestNeutralization(unittest.TestCase):
    def test_cross_section_z_mean_near_zero(self) -> None:
        vals = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0, "E": 5.0}
        z = cross_section_z(vals)
        mean = sum(z.values()) / len(z)
        self.assertAlmostEqual(mean, 0.0, places=5)

    def test_industry_neutral_removes_industry_mean(self) -> None:
        vals = {"A": 10.0, "B": 12.0, "C": 1.0, "D": 2.0}
        ind = {"A": "X", "B": "X", "C": "Y", "D": "Y"}
        z = industry_neutral_zscores(vals, ind)
        self.assertAlmostEqual(z["A"], -z["B"], delta=0.5)

    def test_size_neutral_reduces_cap_correlation(self) -> None:
        syms = [f"S{i}" for i in range(10)]
        vals = {s: float(i) for i, s in enumerate(syms)}
        log_cap = {s: math.log(100 + i * 50) for i, s in enumerate(syms)}
        ind = {s: "Z" for s in syms}
        raw_corr = _corr(list(vals.values()), list(log_cap.values()))
        neu = neutralize_size_industry(vals, log_market_cap=log_cap, industries=ind)
        neu_corr = _corr(list(neu.values()), list(log_cap.values()))
        self.assertLess(abs(neu_corr), abs(raw_corr))


def _corr(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((x - mb) ** 2 for x in b))
    return num / (da * db) if da and db else 0.0


if __name__ == "__main__":
    unittest.main()
