from quant.portfolio.constraints import DEFAULT_CONSTRAINTS
from quant.portfolio.optimizer import optimize_topk


def test_portfolio_spec_constraints():
    assert DEFAULT_CONSTRAINTS.max_single_weight == 0.05
    assert DEFAULT_CONSTRAINTS.max_industry_weight == 0.15


def test_optimizer_respects_single_name_cap():
    cands = [
        {"symbol": f"60000{i}.SH", "score": 10 - i, "sector": "银行", "name": f"T{i}"}
        for i in range(10)
    ]
    out = optimize_topk(cands, top_k=5)
    assert all(w <= 0.05 + 1e-6 for w in out["weights"].values())
