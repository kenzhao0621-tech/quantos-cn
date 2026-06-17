"""Calibration metrics — Brier, log loss, ECE. Returns INSUFFICIENT_SAMPLE when n too small."""

from __future__ import annotations

import math
import statistics
from typing import Any

MIN_CALIBRATION_SAMPLES = 30


def brier_score(predictions: list[float], outcomes: list[int]) -> float | None:
    if len(predictions) != len(outcomes) or len(predictions) < 5:
        return None
    return statistics.fmean((p - o) ** 2 for p, o in zip(predictions, outcomes))


def log_loss(predictions: list[float], outcomes: list[int], *, eps: float = 1e-6) -> float | None:
    if len(predictions) != len(outcomes) or len(predictions) < 5:
        return None
    total = 0.0
    for p, o in zip(predictions, outcomes):
        p = min(max(p, eps), 1.0 - eps)
        total -= o * math.log(p) + (1 - o) * math.log(1 - p)
    return total / len(predictions)


def expected_calibration_error(predictions: list[float], outcomes: list[int], *, n_bins: int = 10) -> float | None:
    if len(predictions) != len(outcomes) or len(predictions) < MIN_CALIBRATION_SAMPLES:
        return None
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, o in zip(predictions, outcomes):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, o))
    ece = 0.0
    n = len(predictions)
    for bucket in bins:
        if not bucket:
            continue
        avg_p = statistics.fmean(p for p, _ in bucket)
        avg_o = statistics.fmean(o for _, o in bucket)
        ece += len(bucket) / n * abs(avg_p - avg_o)
    return ece


def summarize_calibration(predictions: list[float], outcomes: list[int]) -> dict[str, Any]:
    n = len(predictions)
    if n < MIN_CALIBRATION_SAMPLES:
        return {
            "status": "INSUFFICIENT_SAMPLE",
            "n_samples": n,
            "min_required": MIN_CALIBRATION_SAMPLES,
        }
    brier = brier_score(predictions, outcomes)
    ll = log_loss(predictions, outcomes)
    ece = expected_calibration_error(predictions, outcomes)
    return {
        "status": "OK",
        "n_samples": n,
        "brier_score": round(brier, 4) if brier is not None else None,
        "log_loss": round(ll, 4) if ll is not None else None,
        "expected_calibration_error": round(ece, 4) if ece is not None else None,
        "calibration_valid": ece is not None and ece < 0.15,
    }
