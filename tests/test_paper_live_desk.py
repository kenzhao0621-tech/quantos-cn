"""Live market service + paper desk tests."""

import json
from pathlib import Path

from gateway.brokers.paper import PaperBrokerAdapter
from gateway.config import ROOT
from gateway.risk.engine import OrderIntent, RiskEngine
from gateway.risk.kill_switch import KillSwitch
from gateway.config import GatewayConfig


def test_snapshot_rows_from_attempts_payload():
    from quant.application.live_market_service import snapshot_rows, live_price_map, normalize_ts_code

    nested = {
        "row_count": 2,
        "attempts": [
            {
                "status": "SUCCESS",
                "payload": {
                    "rows": [
                        {"code": "sh600519", "price": 1800.5, "change_pct": 0.5},
                        {"code": "sz000001", "price": 12.3, "change_pct": -0.2},
                    ]
                },
            }
        ],
    }
    rows = snapshot_rows(nested)
    assert len(rows) == 2
    assert normalize_ts_code("sh600519") == "600519.SH"


def test_ensure_live_quotes_persists_rows(tmp_path, monkeypatch):
    from quant.application import live_market_service as lms

    fake_rows = [{"code": "600519", "name": "茅台", "price": 100.0, "change_pct": 1.2, "amount": 1e9}] * 150
    snap = {
        "success": True,
        "row_count": len(fake_rows),
        "rows": fake_rows,
        "retrieved_at": "2026-06-18T10:00:00+00:00",
        "provider": "test",
    }
    monkeypatch.setattr(lms, "fetch_live_snapshot", lambda require_live=False: snap)
    live_path = tmp_path / "live_snapshot.json"
    monkeypatch.setattr(lms, "LIVE_STATE_PATH", live_path)
    out = lms.ensure_live_quotes(refresh=True)
    assert out["row_count"] >= 100
    assert live_path.exists()
    saved = json.loads(live_path.read_text(encoding="utf-8"))
    assert len(saved.get("rows") or []) >= 100


def test_risk_snapshot_no_live_blocker_in_paper_mode():
    cfg = GatewayConfig.load()
    cfg.paper_trading_only = True
    cfg.real_money_execution_disabled = True
    cfg.enable_live_trading = False
    risk = RiskEngine(cfg, KillSwitch())
    snap = risk.snapshot()
    assert "LIVE_TRADING_NOT_APPROVED_THIS_BATCH" not in snap.blockers


def test_risk_snapshot_live_blocker_when_real_enabled_without_batch():
    cfg = GatewayConfig.load()
    cfg.paper_trading_only = False
    cfg.real_money_execution_disabled = False
    cfg.enable_live_trading = True
    cfg.live_trading_batch_approved = False
    risk = RiskEngine(cfg, KillSwitch())
    snap = risk.snapshot()
    assert "LIVE_TRADING_NOT_APPROVED_THIS_BATCH" in snap.blockers


def test_live_quotes_ready_nested_rows():
    from quant.application.live_market_service import live_quotes_ready

    assert live_quotes_ready({"blocked": False, "attempts": [{"status": "SUCCESS", "payload": {"rows": [{"code": "1"}] * 120}}]})
    assert not live_quotes_ready({"blocked": True, "rows": [{"code": "1"}] * 200})


def test_trading_agents_zh_overlay():
    from gateway.agents.cn_research.screener_bridge import apply_trading_agents_zh_overlay

    rows = [{
        "symbol": "600519.SH",
        "ret_20": 0.08,
        "trend": 0.03,
        "vol_20": 2.0,
        "score": 1.5,
        "live_pct": 1.2,
    }]
    out, meta = apply_trading_agents_zh_overlay(
        rows,
        as_of_date="2026-06-18",
        mode="eod",
        live_status={"used": False},
        fast=True,
    )
    assert meta["panel"]["framework"] == "TradingAgents-CN"
    assert "600519.SH" in meta["overlays"]
    assert out[0]["symbol"] == "600519.SH"


def test_paper_manual_order_and_persist(tmp_path, monkeypatch):
    from gateway.brokers import paper_store

    state_path = tmp_path / "paper_state.json"
    monkeypatch.setattr(paper_store, "STATE_PATH", state_path)

    cfg = GatewayConfig.load()
    risk = RiskEngine(cfg, KillSwitch())
    risk.set_mode("PAPER_TRADING")
    broker = PaperBrokerAdapter(risk)
    broker.cash_cny = 100000.0

    intent = OrderIntent(
        client_order_id="test-1",
        run_id="run1",
        strategy_id="desk",
        model_id="paper",
        symbol="000001.SZ",
        side="BUY",
        quantity=100,
        limit_price=10.0,
        notional_cny=1000.0,
    )
    order = broker.submit(intent, data_fresh=True, market_price=10.0)
    assert order.state.value == "FILLED", order.reject_reason
    assert state_path.exists()
    assert broker.positions.get("000001.SZ") is not None
