"""Factor normalization to 0-100 (v2.2 §5.3).

Cross-sectional percentile with 5%/95% winsorization is the default. Missing
values are NEVER given a high score — they map to the neutral 50 and must be
flagged by the caller. Lower-is-better factors are inverted explicitly.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

NEUTRAL_SCORE = 50.0
NORMALIZATION_METHOD = "robust_percentile_winsor_5_95"


def _percentile_of(x: float, sorted_values: List[float]) -> float:
    """Fraction of values strictly below x plus half the ties (midrank)."""
    n = len(sorted_values)
    if n == 0:
        return 0.5
    below = sum(1 for v in sorted_values if v < x)
    ties = sum(1 for v in sorted_values if v == x)
    return (below + 0.5 * ties) / n


def winsorize(values: List[float], lower_pct: float = 0.05, upper_pct: float = 0.95) -> List[float]:
    if not values:
        return []
    s = sorted(values)
    n = len(s)
    lo = s[max(0, min(n - 1, int(lower_pct * (n - 1))))]
    hi = s[max(0, min(n - 1, int(upper_pct * (n - 1))))]
    return [min(max(v, lo), hi) for v in values]


def robust_percentile_score(
    x: Optional[float],
    cross_section_values: Iterable[Optional[float]],
    *,
    lower_is_better: bool = False,
) -> float:
    """Convert raw factor value into 0-100 score by cross-sectional percentile.

    Winsorize at 5% and 95% to reduce outlier impact. Missing input returns the
    neutral 50 — callers must record the factor as missing/down-weighted.
    """
    if x is None or x != x:  # None or NaN
        return NEUTRAL_SCORE
    clean = [float(v) for v in cross_section_values if v is not None and v == v]
    if not clean:
        return NEUTRAL_SCORE
    wins = winsorize(clean)
    lo, hi = min(wins), max(wins)
    x_w = min(max(float(x), lo), hi)
    pct = _percentile_of(x_w, sorted(wins))
    score = pct * 100.0
    if lower_is_better:
        score = 100.0 - score
    return round(min(100.0, max(0.0, score)), 2)


def clamp_score(x: float) -> float:
    return min(100.0, max(0.0, float(x)))


def weighted_subscores(pairs: List) -> float:
    """Weighted sum of (weight, score_0_100) pairs, clamped to 0-100.

    Weights are renormalized over present pairs so a documented sub-factor
    breakdown always maps back to the published weights.
    """
    total_w = sum(w for w, _ in pairs)
    if total_w <= 0:
        return NEUTRAL_SCORE
    return clamp_score(sum(w * clamp_score(s) for w, s in pairs) / total_w)
