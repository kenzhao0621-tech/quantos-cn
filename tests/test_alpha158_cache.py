"""Alpha158 cache and feature dimension tests."""

from __future__ import annotations

import unittest

from quant.features.alpha158 import FEATURE_VERSION, compute_alpha158_frame, feature_column_names


class TestAlpha158(unittest.TestCase):
    def test_feature_count_is_158(self) -> None:
        self.assertEqual(len(feature_column_names()), 158)

    def test_compute_from_synthetic_bars(self) -> None:
        import pandas as pd

        rows = []
        for i in range(80):
            rows.append({
                "ts_code": "600000.SH",
                "trade_date": f"2026-01-{i+1:02d}" if i < 31 else f"2026-02-{(i-30):02d}",
                "open": 10 + i * 0.01,
                "high": 10.5 + i * 0.01,
                "low": 9.5 + i * 0.01,
                "close": 10 + i * 0.02,
                "vol": 1e6 + i * 1000,
                "amount": 1e7 + i * 10000,
            })
        df = pd.DataFrame(rows)
        out = compute_alpha158_frame(df)
        self.assertGreater(len(out), 0)
        self.assertEqual(len([c for c in feature_column_names() if c in out.columns]), 158)

    def test_manifest_exists_after_build(self) -> None:
        from pathlib import Path

        manifest = Path(__file__).resolve().parents[1] / "artifacts" / "alpha158_cache_manifest.json"
        if not manifest.exists():
            self.skipTest("run scripts/build_alpha158_cache.py first")
        import json

        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertTrue(data.get("built"))
        self.assertEqual(data.get("feature_version"), FEATURE_VERSION)
        self.assertEqual(data.get("n_features"), 158)


if __name__ == "__main__":
    unittest.main()
