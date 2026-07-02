"""v2.2 §12.2 acceptance: weight sum, 0-100 bounds, reproducibility, missing-data
down-weighting, penalties, hard blocks, version tracking."""

import json

import pytest

from quant.scoring_os.formulas import (
    SUB_WEIGHTS,
    FactorScore,
    ScoreInputs,
    compose_factor,
    compute_final_score,
)
from quant.scoring_os.weights import BASE_WEIGHTS, SCORE_WEIGHT_VERSION, get_weight_set


def _full_factors(score=70.0):
    return {
        name: FactorScore(name=name, score=score, source="tushare",
                          source_url="https://tushare.pro", updated_at="2026-07-01 15:30:00",
                          freshness="fresh")
        for name in BASE_WEIGHTS
    }


def _tiers():
    return {name: "A_public_data_vendor" for name in BASE_WEIGHTS}


def test_base_weights_sum_to_one():
    assert sum(BASE_WEIGHTS.values()) == pytest.approx(1.0)


def test_all_sub_weight_groups_sum_to_one():
    for factor, weights in SUB_WEIGHTS.items():
        assert sum(weights.values()) == pytest.approx(1.0), factor


def test_final_score_reproducible():
    inputs = ScoreInputs(
        symbol="600519.SH", factors=_full_factors(), regime="range_bound",
        source_tiers=_tiers(),
        risk_inputs={"volatility_risk": 40, "drawdown_risk": 30},
        execution_inputs={"lot_size": 20},
        overheat_inputs={"short_term_return_overheat": 50},
    )
    a = compute_final_score(inputs)
    b = compute_final_score(inputs)
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def test_score_within_bounds_at_extremes():
    hi = compute_final_score(ScoreInputs(
        symbol="X", factors=_full_factors(100.0), regime="strong_bull", source_tiers=_tiers()))
    lo = compute_final_score(ScoreInputs(
        symbol="X", factors=_full_factors(0.0), regime="bear", source_tiers=_tiers(),
        risk_inputs={k: 100 for k in ("volatility_risk", "drawdown_risk", "fundamental_risk",
                                      "event_risk", "liquidity_risk", "concentration_risk")},
        execution_inputs={k: 100 for k in ("lot_size", "price_limit", "slippage", "t_plus_one", "cash_fit")},
        overheat_inputs={k: 100 for k in ("short_term_return_overheat", "volume_spike_risk",
                                          "limit_up_chase_risk", "valuation_overheat",
                                          "sentiment_crowding_risk")},
    ))
    assert 0.0 <= lo["final_score"] <= hi["final_score"] <= 100.0


def test_version_recorded_and_weight_lookup_strict():
    res = compute_final_score(ScoreInputs(symbol="X", factors=_full_factors(), source_tiers=_tiers()))
    assert res["score_weight_version"] == SCORE_WEIGHT_VERSION
    assert get_weight_set()["score_weight_version"] == SCORE_WEIGHT_VERSION
    with pytest.raises(KeyError):
        get_weight_set("v9.9_made_up")


def test_missing_factor_down_weighted_not_high_scored():
    factors = _full_factors(90.0)
    del factors["kronos_forecast"]  # model unavailable
    res = compute_final_score(ScoreInputs(symbol="X", factors=factors,
                                          regime="range_bound", source_tiers=_tiers()))
    assert "kronos_forecast" in res["missing_factors"]
    kro = next(c for c in res["contributions"] if c["factor"] == "kronos_forecast")
    assert kro["missing"] and kro["score"] == 50.0
    assert kro["effective_weight"] == pytest.approx(BASE_WEIGHTS["kronos_forecast"] * 0.5)
    full = compute_final_score(ScoreInputs(symbol="X", factors=_full_factors(90.0),
                                           regime="range_bound", source_tiers=_tiers()))
    assert res["base_opportunity_score"] < full["base_opportunity_score"]
    # data quality multiplier also drops because the factor's source is missing
    assert res["data_quality_multiplier"] < full["data_quality_multiplier"]


def test_risk_penalty_reduces_final_score():
    base_inputs = ScoreInputs(symbol="X", factors=_full_factors(), source_tiers=_tiers())
    no_risk = compute_final_score(base_inputs)
    risky = compute_final_score(ScoreInputs(
        symbol="X", factors=_full_factors(), source_tiers=_tiers(),
        risk_inputs={"volatility_risk": 100, "drawdown_risk": 100, "fundamental_risk": 100,
                     "event_risk": 100, "liquidity_risk": 100, "concentration_risk": 100}))
    assert risky["risk_penalty"]["points"] == pytest.approx(30.0)
    assert risky["final_score"] == pytest.approx(no_risk["final_score"] - 30.0, abs=0.05)


def test_overheat_stock_penalized():
    calm = compute_final_score(ScoreInputs(symbol="X", factors=_full_factors(85), source_tiers=_tiers()))
    hot = compute_final_score(ScoreInputs(
        symbol="X", factors=_full_factors(85), source_tiers=_tiers(),
        overheat_inputs={"short_term_return_overheat": 95, "volume_spike_risk": 80,
                         "limit_up_chase_risk": 90, "valuation_overheat": 70,
                         "sentiment_crowding_risk": 85}))
    assert hot["final_score"] < calm["final_score"]
    assert hot["overheat_penalty"]["points"] > 10


def test_st_stock_hard_blocked():
    res = compute_final_score(ScoreInputs(
        symbol="600XXX.SH", factors=_full_factors(95), source_tiers=_tiers(),
        risk_inputs={"is_st": True}))
    assert res["hard_blocked"]
    assert any("ST" in r for r in res["hard_block_reasons"])


def test_unverifiable_data_hard_blocked():
    res = compute_final_score(ScoreInputs(
        symbol="X", factors=_full_factors(), source_tiers=_tiers(),
        risk_inputs={"data_unverifiable": True}))
    assert res["hard_blocked"]


def test_unknown_regime_treated_conservatively():
    res = compute_final_score(ScoreInputs(symbol="X", factors=_full_factors(),
                                          regime="martian_bull", source_tiers=_tiers()))
    assert res["regime"] == "unknown"
    assert res["regime_multiplier"] == 0.85


def test_contribution_breakdown_complete_and_consistent():
    res = compute_final_score(ScoreInputs(symbol="X", factors=_full_factors(70),
                                          regime="range_bound", source_tiers=_tiers()))
    assert {c["factor"] for c in res["contributions"]} == set(BASE_WEIGHTS)
    total_contrib = sum(c["contribution"] for c in res["contributions"])
    assert total_contrib == pytest.approx(res["base_opportunity_score"], abs=0.15)
    for c in res["contributions"]:
        assert c["source_url"]  # every factor traceable
        assert c["updated_at"]


def test_compose_factor_renormalizes_missing_subscores():
    full = compose_factor("trend", {"ma_alignment": 80, "breakout": 60,
                                    "relative_strength": 70, "drawdown_recovery": 50})
    partial = compose_factor("trend", {"ma_alignment": 80, "breakout": None,
                                       "relative_strength": 70, "drawdown_recovery": None})
    assert 0 <= full["score"] <= 100
    expected = (0.35 * 80 + 0.20 * 70) / (0.35 + 0.20)
    assert partial["score"] == pytest.approx(expected, abs=0.01)
    assert sum(1 for d in partial["sub_factors"] if d["missing"]) == 2


def test_compose_factor_all_missing_is_neutral():
    res = compose_factor("sentiment", {})
    assert res["score"] == 50.0
    assert res["all_missing"]
