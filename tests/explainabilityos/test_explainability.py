from quant.explain.factor_contribution import explain_candidate


def test_explain_forbids_hype():
    out = explain_candidate({"symbol": "600519.SH", "score": 0.8, "factor_breakdown": []})
    assert "forbidden_phrases" in out
    assert "保证收益" in out["forbidden_phrases"]
