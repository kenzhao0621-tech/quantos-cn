"""Unified portfolio builder tests."""

from quant.portfolio.unified import build_portfolio_allocation


def test_unified_portfolio_respects_constraints():
    cands = [
        {
            "symbol": "600519.SH",
            "name": "茅台",
            "last_close": 100.0,
            "score": 0.9,
            "valid_for_purchase": True,
            "sector": "消费",
        },
        {
            "symbol": "000001.SZ",
            "name": "平安",
            "last_close": 10.0,
            "score": 0.8,
            "valid_for_purchase": True,
            "sector": "金融",
        },
    ]
    out = build_portfolio_allocation(cands, capital_cny=50000.0, max_holdings=2)
    assert out["n_positions"] >= 1
    for p in out["positions"]:
        assert p["quantity"] % 100 == 0
        assert p["weight"] <= 0.05 + 1e-6
