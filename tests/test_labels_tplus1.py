"""T+1 label semantics — no future function in signal date."""

from __future__ import annotations

import unittest

from quant.labels import label_close_to_close, rank_label_buckets


class TestLabelsTplus1(unittest.TestCase):
    def test_label_uses_next_day_entry(self) -> None:
        dates = ["D0", "D1", "D2", "D3"]
        close = {"D0": 10.0, "D1": 10.0, "D2": 11.0, "D3": 12.0}
        lab = label_close_to_close(close, dates, signal_idx=0, horizon=1)
        self.assertAlmostEqual(lab, 0.1, places=5)

    def test_rank_buckets(self) -> None:
        buckets = rank_label_buckets([0.1, 0.2, 0.3, 0.4, 0.5], n_buckets=5)
        self.assertEqual(len(buckets), 5)


if __name__ == "__main__":
    unittest.main()
