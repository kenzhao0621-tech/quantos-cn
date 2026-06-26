#!/usr/bin/env python3
"""Train LightGBM LambdaRank on Alpha158 sample (CSI300 proxy universe)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ART = ROOT / "artifacts"


def main() -> int:
    p = argparse.ArgumentParser(description="Train LGBM ranker on Alpha158 cache")
    p.add_argument("--horizon", type=int, default=5, help="Forward return horizon (T+1 entry)")
    p.add_argument("--force-cache", action="store_true")
    args = p.parse_args()

    from quant.features.alpha158 import feature_column_names
    from quant.features.alpha158_cache import build_alpha158_cache, load_alpha158_wide
    from quant.labels import rank_label_buckets
    from quant.models.lgbm_ranker import predict_ranker, train_ranker
    from quant.validation.rank_ic import daily_rank_ic, summarize_rank_ic

    manifest = build_alpha158_cache(mode="sample", sample_size=300, force=args.force_cache)
    if not manifest.get("built"):
        print(json.dumps({"ok": False, "error": manifest.get("error", "cache build failed")}, indent=2))
        return 1

    wide = load_alpha158_wide()
    feat_cols = [c for c in feature_column_names() if c in wide.columns]

    import duckdb

    wh = ROOT / "data" / "warehouse" / "quant.duckdb"
    con = duckdb.connect(str(wh), read_only=True)
    px = con.execute(
        """
        SELECT ts_code, trade_date, close
        FROM daily_bars
        WHERE ts_code IN (SELECT DISTINCT ts_code FROM read_parquet(?))
        ORDER BY ts_code, trade_date
        """,
        [str(ROOT / manifest["path"])],
    ).fetchdf()
    con.close()

    px["trade_date"] = px["trade_date"].astype(str)
    px = px.sort_values(["ts_code", "trade_date"])
    h = args.horizon
    entry = px.groupby("ts_code")["close"].shift(-1)
    exit_ = px.groupby("ts_code")["close"].shift(-(h + 1))
    px["label"] = exit_.astype(float) / entry.astype(float) - 1.0
    labels = px[["ts_code", "trade_date", "label"]].dropna()

    merged = wide.merge(labels, on=["ts_code", "trade_date"], how="inner")
    merged = merged.replace([float("inf"), float("-inf")], pd.NA).fillna(0.0)
    if len(merged) < 500:
        print(json.dumps({"ok": False, "error": "insufficient merged rows", "n": len(merged)}, indent=2))
        return 1

    dates = sorted(merged["trade_date"].unique())
    split_idx = int(len(dates) * 0.8)
    train_dates = set(dates[:split_idx])
    test_dates = set(dates[split_idx:])

    X_train: list[list[float]] = []
    y_train: list[int] = []
    groups: list[int] = []
    train_frames: list[pd.DataFrame] = []

    for d in dates[:split_idx]:
        g = merged[merged["trade_date"] == d].dropna(subset=["label"])
        if len(g) < 10:
            continue
        buckets = rank_label_buckets(g["label"].tolist(), n_buckets=5)
        for i, (_, row) in enumerate(g.iterrows()):
            X_train.append([float(row[c]) for c in feat_cols])
            y_train.append(buckets[i])
        groups.append(len(g))
        train_frames.append(g.assign(pred_slot=range(len(g))))

    train_info = train_ranker(X_train, y_train, groups, feature_names=feat_cols)

    # Predict on test slice
    test_rows: list[pd.DataFrame] = []
    X_test: list[list[float]] = []
    for d in dates[split_idx:]:
        g = merged[merged["trade_date"] == d].dropna(subset=["label"])
        if len(g) < 5:
            continue
        for _, row in g.iterrows():
            X_test.append([float(row[c]) for c in feat_cols])
        test_rows.append(g)

    preds = predict_ranker(X_test) or []
    daily_ics: list[float | None] = []
    off = 0
    for g in test_rows:
        n = len(g)
        scores = {sym: preds[off + i] for i, sym in enumerate(g["ts_code"].tolist())}
        rets = {sym: float(lab) for sym, lab in zip(g["ts_code"], g["label"])}
        daily_ics.append(daily_rank_ic(scores, rets))
        off += n

    ric = summarize_rank_ic(daily_ics)
    metrics = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "train": train_info,
        "feature_version": manifest.get("feature_version"),
        "n_samples_train": len(X_train),
        "n_groups_train": len(groups),
        "n_features": len(feat_cols),
        "horizon": h,
        "rank_ic_oos": ric,
        "universe": "csi300_proxy_top300_liquid",
        "train_dates": f"{dates[0]}..{dates[split_idx-1]}",
        "test_dates": f"{dates[split_idx]}..{dates[-1]}",
    }

    ART.mkdir(parents=True, exist_ok=True)
    (ART / "model_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    registry = {
        "model_id": "alpha158_lgbm_ranker_sample",
        "status": "CANDIDATE" if ric.get("mean_rank_ic", 0) >= 0.01 else "REJECTED",
        "metrics_path": "artifacts/model_metrics.json",
        "manifest_path": "artifacts/alpha158_cache_manifest.json",
    }
    (ART / "model_registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "train": train_info, "rank_ic_oos": ric, "registry": registry}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
