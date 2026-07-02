"""Normalization (§5.3), confidence bands (§6.6), trade plan structure (§7)."""

import pytest

from quant.scoring_os.confidence import compute_confidence
from quant.scoring_os.normalization import robust_percentile_score, winsorize
from quant.scoring_os.target_price import LOT_SIZE, build_trade_plan, compute_atr


# ---------------------------------------------------------------- normalization
def test_percentile_score_in_bounds_and_monotone():
    xs = list(range(100))
    lo = robust_percentile_score(5, xs)
    mid = robust_percentile_score(50, xs)
    hi = robust_percentile_score(95, xs)
    assert 0 <= lo < mid < hi <= 100


def test_lower_is_better_inverts():
    xs = list(range(100))
    assert robust_percentile_score(90, xs, lower_is_better=True) < 20


def test_missing_value_is_neutral_not_high():
    assert robust_percentile_score(None, [1, 2, 3]) == 50.0
    assert robust_percentile_score(float("nan"), [1, 2, 3]) == 50.0


def test_winsorize_caps_outliers():
    vals = [1.0] * 98 + [1000.0, -1000.0]
    w = winsorize(vals)
    assert max(w) < 1000 and min(w) > -1000


def test_outlier_does_not_dominate_percentile():
    xs = [1, 2, 3, 4, 5, 10000]
    assert robust_percentile_score(5, xs) > 60


# ---------------------------------------------------------------- confidence
def test_confidence_weights_sum_to_one():
    from quant.scoring_os.confidence import CONFIDENCE_WEIGHTS

    assert sum(CONFIDENCE_WEIGHTS.values()) == pytest.approx(1.0)


def test_confidence_bands():
    low = compute_confidence({"signal_agreement": 0.2, "data_freshness": 0.3})
    assert low["band"] == "low" and not low["actionable"]
    full = {k: 1.0 for k in ("signal_agreement", "data_freshness",
                             "historical_validation_strength", "regime_clarity", "model_stability")}
    top = compute_confidence(full)
    assert top["band"] == "exceptional"
    mid = compute_confidence({k: 0.65 for k in full})
    assert mid["band"] == "medium" and mid["actionable"]


def test_confidence_missing_components_score_zero():
    res = compute_confidence({"signal_agreement": 1.0})
    assert res["confidence"] == pytest.approx(0.30)
    assert len(res["missing_components"]) == 4


# ---------------------------------------------------------------- trade plan
def _history(n=80, base=10.0, drift=0.001):
    bars = []
    price = base
    for i in range(n):
        price *= 1 + drift
        bars.append({"open": price * 0.995, "high": price * 1.02,
                     "low": price * 0.98, "close": price})
    return bars


def test_atr_needs_enough_history():
    assert compute_atr(_history(5)) is None
    assert compute_atr(_history(30)) is not None


def test_trade_plan_structure_and_ordering():
    hist = _history()
    price = hist[-1]["close"]
    plan = build_trade_plan(symbol="600519.SH", current_price=price, history=hist,
                            capital_cny=100000, position_weight=0.3)
    assert plan["recommendation"] in ("buy_zone", "watch")
    if plan["buy_zone"]:
        lo, hi = plan["buy_zone"]
        assert plan["stop_loss"] < lo <= hi
        assert plan["stop_loss"] < plan["target_1"] <= plan["target_2"]
        assert plan["risk_reward_ratio"] >= 1.0
        assert plan["shares"] % LOT_SIZE == 0
        assert plan["do_not_buy_conditions"]
        assert plan["basis"]["stop_components"]["atr_stop"] is not None


def test_trade_plan_insufficient_history_says_so():
    plan = build_trade_plan(symbol="600519.SH", current_price=10.0, history=_history(10))
    assert plan["recommendation"] == "insufficient_structure"
    assert plan["shares"] == 0


def test_trade_plan_small_account_lot_warning():
    hist = _history(base=500.0)  # ~540 CNY/share → one lot > 54000 CNY
    plan = build_trade_plan(symbol="600519.SH", current_price=hist[-1]["close"],
                            history=hist, capital_cny=5000, position_weight=0.5)
    if plan["recommendation"] != "insufficient_structure" and plan.get("buy_zone"):
        assert plan["shares"] == 0
        assert "一手" in plan["minimum_lot_warning"]
        assert plan["recommendation"] == "watch"


def test_trade_plan_limit_up_forbids_chase():
    hist = _history()
    plan = build_trade_plan(symbol="000001.SZ", current_price=hist[-1]["close"],
                            history=hist, capital_cny=50000, last_pct=9.9)
    assert any("涨停" in c for c in plan["do_not_buy_conditions"])
    assert plan["recommendation"] != "buy_zone"


def test_trade_plan_gap_up_forbids_chase():
    hist = _history()
    plan = build_trade_plan(symbol="000001.SZ", current_price=hist[-1]["close"],
                            history=hist, capital_cny=50000, open_gap_pct=6.5)
    assert any("高开" in c for c in plan["do_not_buy_conditions"])


def test_trade_plan_reproducible():
    hist = _history()
    kw = dict(symbol="600519.SH", current_price=hist[-1]["close"], history=hist,
              capital_cny=20000, position_weight=0.3)
    assert build_trade_plan(**kw) == build_trade_plan(**kw)
