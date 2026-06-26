"""Paper autopilot monitor tests."""

from gateway.paper.autopilot_monitor import load_monitor_state, run_monitor_tick, set_monitor_portfolio


def test_monitor_blocked_without_live_quotes(monkeypatch):
    from gateway.brokers.paper import PaperBrokerAdapter
    from gateway.config import GatewayConfig
    from gateway.risk.engine import RiskEngine
    from gateway.risk.kill_switch import KillSwitch

    monkeypatch.setattr(
        "gateway.paper.autopilot_monitor._fetch_real_prices",
        lambda refresh=True: ({}, {"blocked": True, "quote_count": 0}),
    )
    set_monitor_portfolio([{"symbol": "600519.SH", "name": "茅台", "trade_zones": {"buy_zone_low": 1, "buy_zone_high": 9999}}], enabled=True)
    risk = RiskEngine(GatewayConfig.load(), KillSwitch())
    risk.set_mode("PAPER_TRADING")
    paper = PaperBrokerAdapter(risk)
    out = run_monitor_tick(paper, user_id="test")
    assert out["ok"] is False
    assert "实时行情" in out.get("reason", "")
    st = load_monitor_state()
    assert st.get("last_error")
