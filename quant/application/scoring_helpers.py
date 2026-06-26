"""Shared screener row scoring + ensemble finalization."""

from __future__ import annotations

from typing import Any


def assign_baseline_scores(
    raw: list[dict[str, Any]],
    z: dict[str, dict[str, float]],
    weights: dict[str, float],
    *,
    preset: str,
    mode: str,
    preferred: list[str] | None,
    sector_matches,
    blend_with_alpha,
    alpha158_lite_zscore,
    factor_breakdown,
) -> None:
    """Compute baseline_score, live component, and pre-ensemble score on each row."""
    for r in raw:
        sym = r["symbol"]
        base_score = (
            weights["ret_20"] * z["ret_20"][sym]
            + weights["ret_60"] * z["ret_60"][sym]
            + weights["trend"] * z["trend"][sym]
            - weights["vol_penalty"] * z["vol_20"][sym]
        )
        alpha_score = alpha158_lite_zscore(r, z)
        r["alpha_score"] = alpha_score
        r["factor_breakdown"] = factor_breakdown(r, z, weights)
        live_score = 0.0
        if "live_pct" in z and r.get("live_pct") is not None:
            if preset == "momentum":
                live_score += 1.15 * z["live_pct"].get(sym, 0.0) + 0.35 * z["live_amount"].get(sym, 0.0)
            elif preset == "low_vol":
                live_score += 0.35 * z["live_pct"].get(sym, 0.0)
            else:
                live_score += 0.85 * z["live_pct"].get(sym, 0.0) + 0.25 * z["live_amount"].get(sym, 0.0)
            if float(r.get("live_pct") or 0) >= 9.8:
                live_score -= 3.0
        sector_bonus = 0.0
        if preferred and sector_matches(r.get("sector", ""), preferred):
            sector_bonus = 1.2
        quality_score = 0.0
        if "pe" in z and r.get("pe") is not None and float(r["pe"]) > 0:
            quality_score += -0.16 * z["pe"].get(sym, 0.0)
        if "pb" in z and r.get("pb") is not None and float(r["pb"]) > 0:
            quality_score += -0.12 * z["pb"].get(sym, 0.0)
        if "dividend_yield" in z and r.get("dividend_yield") is not None:
            quality_score += 0.10 * z["dividend_yield"].get(sym, 0.0)
        disclosure_penalty = -1.0 if str(r.get("disclosure_flag", "")).upper() in {"HIGH", "MEDIUM"} else 0.0
        blended = blend_with_alpha(base_score + sector_bonus + quality_score + disclosure_penalty, alpha_score)
        r["baseline_score"] = blended
        r["live_score_component"] = live_score
        if mode.lower() in ("live", "realtime", "intraday") and "live_pct" in z:
            r["score"] = 0.45 * blended + live_score
        else:
            r["score"] = blended


def finalize_with_ensemble(
    raw: list[dict[str, Any]],
    *,
    as_of_date: str | None,
    z: dict[str, dict[str, float]],
    mode: str,
    fast: bool = False,
) -> dict[str, Any]:
    from quant.models.ml_scorer import apply_ensemble_to_rows

    return apply_ensemble_to_rows(raw, as_of_date=as_of_date, z=z, mode=mode, fast=fast)
