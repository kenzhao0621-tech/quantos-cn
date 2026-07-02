"""v2.2 §12.3 acceptance: four panels, provenance, formula/cache/update display,
forbidden-language rejection."""

import pytest

from quant.explain_os.advice_card import build_advice_card
from quant.explain_os.language_guard import check_text, scrub_payload
from quant.explain_os.score_breakdown import build_score_breakdown
from quant.scoring_os.confidence import compute_confidence
from quant.scoring_os.formulas import FactorScore, ScoreInputs, compute_final_score
from quant.scoring_os.weights import BASE_WEIGHTS, SCORE_WEIGHT_VERSION


def _score_result(**risk):
    factors = {
        name: FactorScore(name=name, score=72.0, source="tushare",
                          source_url="https://tushare.pro", updated_at="2026-07-01 15:30:00",
                          freshness="fresh")
        for name in BASE_WEIGHTS
    }
    return compute_final_score(ScoreInputs(
        symbol="600519.SH", factors=factors, regime="range_bound",
        source_tiers={n: "A_public_data_vendor" for n in BASE_WEIGHTS},
        risk_inputs=risk,
    ))


def _card(score_result=None, facts=None, plan=None, conf=None):
    return build_advice_card(
        symbol="600519.SH",
        name="贵州茅台",
        score_result=score_result or _score_result(),
        trade_plan=plan or {
            "recommendation": "buy_zone", "buy_zone": [1400.0, 1450.0],
            "stop_loss": 1350.0, "target_1": 1550.0, "target_2": 1650.0,
            "risk_reward_ratio": 2.0, "shares": 0, "position_size_rmb": 0,
            "minimum_lot_warning": "资金不足一手", "do_not_buy_conditions": ["高开超过5%不追入"],
        },
        confidence=conf or compute_confidence({
            "signal_agreement": 0.8, "data_freshness": 0.9,
            "historical_validation_strength": 0.5, "regime_clarity": 0.6,
            "model_stability": 0.6,
        }),
        facts=facts if facts is not None else [
            {"fact": "现价 1445.00", "source": "tushare", "source_url": "https://tushare.pro",
             "updated_at": "2026-07-01 15:30:00"},
            {"fact": "无来源的传闻", "source": "股吧"},
        ],
        predictions=[{"model": "kronos-mini", "direction_prob": 0.61, "horizon": "5d"}],
        cache_provenance=[{"cache_status": "hit", "data_type": "advisory_result"}],
        data_freshness_label="最新",
    )


def test_card_has_four_panels():
    card = _card()
    for panel in ("panel_a_verified_facts", "panel_b_quant_computation",
                  "panel_c_model_predictions", "panel_d_conditional_advice"):
        assert panel in card


def test_facts_without_provenance_are_quarantined():
    card = _card()
    assert all(f.get("source_url") and f.get("updated_at") for f in card["panel_a_verified_facts"])
    assert len(card["panel_a_unverified"]) == 1
    assert card["panel_a_unverified"][0]["provenance_missing"]


def test_headline_shows_version_cache_freshness_time():
    h = _card()["headline"]
    assert h["score_weight_version"] == SCORE_WEIGHT_VERSION
    assert h["cache_status"] == "cache_hit"
    assert h["data_freshness"] == "最新"
    assert h["updated_at"]
    assert 1 <= len(h["top_reasons"]) <= 3
    assert 1 <= len(h["top_risks"]) <= 3


def test_predictions_labelled_as_forecast():
    card = _card()
    for p in card["panel_c_model_predictions"]:
        assert p["is_forecast"]
        assert "不保证" in p["disclaimer"]


def test_hard_block_forces_avoid():
    card = _card(score_result=_score_result(is_st=True))
    assert card["headline"]["recommendation"] == "avoid"
    assert card["panel_d_conditional_advice"]["hard_blocked"]


def test_low_confidence_downgrades_buy_to_watch():
    low_conf = compute_confidence({"signal_agreement": 0.2})
    card = _card(conf=low_conf)
    assert card["headline"]["recommendation"] == "watch"


def test_breakdown_lines_match_spec_shape():
    bd = build_score_breakdown(_score_result())
    text = "\n".join(bd["text_lines"])
    assert "综合评分" in text and "市场环境乘数" in text and "最终分" in text
    assert len(bd["factors"]) == len(BASE_WEIGHTS)
    for row in bd["factors"]:
        assert row["source_url"]


def test_forbidden_language_detected_and_scrubbed():
    assert check_text("该股必涨，稳赚不赔") == ["必涨", "稳赚"] or \
        set(check_text("该股必涨，稳赚不赔")) >= {"必涨", "稳赚"}
    payload = {"advice": "主力看好，马上起飞", "nested": [{"t": "保证收益100%"}]}
    cleaned, violations = scrub_payload(payload)
    assert len(violations) == 3
    assert "主力看好" not in cleaned["advice"]
    assert "保证收益" not in cleaned["nested"][0]["t"]


def test_card_output_is_clean_of_forbidden_language():
    facts = [{"fact": "机构正在布局，稳赚", "source": "x", "source_url": "https://x",
              "updated_at": "2026-07-01"}]
    card = _card(facts=facts)
    import json

    violations = card.pop("language_guard_violations", None)
    assert violations  # audit trail records what was scrubbed
    blob = json.dumps(card, ensure_ascii=False)  # user-facing payload
    from quant.explain_os.language_guard import FORBIDDEN_PHRASES

    assert not any(p in blob for p in FORBIDDEN_PHRASES)


def test_do_not_buy_conditions_always_present():
    card = _card()
    assert card["panel_d_conditional_advice"]["do_not_buy_conditions"]
    assert "条件触发" in card["panel_d_conditional_advice"]["condition_note"]
