from quant.execution.a_share_rules import LOT_SIZE, validate_order


def test_lot_size_must_be_100():
    r = validate_order(
        symbol="600519.SH", side="BUY", qty=50, price=100.0,
        last_pct=1.0, avg_amount=1e9, cash=1e6,
    )
    assert not r["valid"]
    assert "invalid_lot_size" in r["reasons"]


def test_a_share_lot_constant():
    assert LOT_SIZE == 100
