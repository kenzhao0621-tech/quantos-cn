"""Historical score bucket statistics — replaces score×constant heuristics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BUCKET_PATH = ROOT / "artifacts" / "score_bucket_stats.json"


def load_bucket_stats() -> dict[str, Any]:
    if BUCKET_PATH.exists():
        return json.loads(BUCKET_PATH.read_text(encoding="utf-8"))
    return {"buckets": [], "status": "NOT_COMPUTED"}


def format_bucket_explanation(score: float, stats: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return user-facing historical bucket stats for a score."""
    stats = stats or load_bucket_stats()
    buckets = stats.get("buckets") or []
    if not buckets:
        return {
            "status": "INSUFFICIENT_HISTORY",
            "summary": "历史分桶统计尚未生成 — 请运行 python scripts/run_quant_upgrade_pipeline.py",
            "disclaimer": "这不是收益承诺，只是历史统计参考。",
        }

    pct = _score_percentile(score, buckets)
    bucket = _pick_bucket(pct, buckets)
    if not bucket:
        return {"status": "NO_MATCH", "summary": "暂无匹配分桶", "disclaimer": stats.get("disclaimer", "")}

    summary = (
        f"该股票当前分数落在历史 Top {100 - pct:.0f}% 桶（约第 {pct:.0f} 百分位）。"
        f"在过去 {bucket.get('n_samples', 'N')} 个样本中，"
        f"该桶 T+5 平均收益 {bucket.get('mean_t5_pct', '—')}%，"
        f"中位数 {bucket.get('median_t5_pct', '—')}%，"
        f"胜率 {bucket.get('win_rate_pct', '—')}%，"
        f"5% 分位亏损 {bucket.get('p5_loss_pct', '—')}%。"
        "这不是收益承诺，只是历史统计参考。"
    )
    return {
        "status": "OK",
        "score_percentile": round(pct, 1),
        "bucket_id": bucket.get("bucket_id"),
        "bucket_label": bucket.get("label"),
        "n_samples": bucket.get("n_samples"),
        "mean_t5_pct": bucket.get("mean_t5_pct"),
        "median_t5_pct": bucket.get("median_t5_pct"),
        "win_rate_pct": bucket.get("win_rate_pct"),
        "p5_loss_pct": bucket.get("p5_loss_pct"),
        "summary": summary,
        "disclaimer": "这不是收益承诺，只是历史统计参考。",
    }


def _score_percentile(score: float, buckets: list[dict[str, Any]]) -> float:
    """Map score to approximate percentile using bucket score bounds."""
    for b in buckets:
        lo, hi = b.get("score_lo"), b.get("score_hi")
        if lo is not None and hi is not None and lo <= score <= hi:
            return float(b.get("percentile_top", 50))
    if buckets:
        if score >= buckets[0].get("score_hi", score):
            return float(buckets[0].get("percentile_top", 10))
        return float(buckets[-1].get("percentile_top", 90))
    return 50.0


def _pick_bucket(pct: float, buckets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for b in buckets:
        top = float(b.get("percentile_top", 100))
        if pct <= top:
            return b
    return buckets[-1] if buckets else None
