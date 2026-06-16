#!/usr/bin/env python3
"""QuantOS CN — vn.py + Qlib integration tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "ai" / "quantos"


class TestEventBridge(unittest.TestCase):
    def test_emit_and_dedupe(self) -> None:
        from integrations.vnpy.event_bridge import EventBridge
        from integrations.vnpy.events import EventType, QuantOSEvent
        with tempfile.TemporaryDirectory() as td:
            import integrations.vnpy.event_bridge as eb
            eb.EVENT_LOG = Path(td) / "events.jsonl"
            bridge = EventBridge()
            ev = QuantOSEvent(event_type=EventType.ORDER, source="test", payload={"x": 1})
            bridge.emit(ev)
            self.assertTrue(bridge.dedupe_check(ev.event_id))
            self.assertEqual(len(bridge.recent()), 1)


class TestOrderIntent(unittest.TestCase):
    def test_board_lot_quantity(self) -> None:
        from integrations.vnpy.order_intent import OrderIntent
        intent = OrderIntent.create(run_id="r1", symbol="600000", exchange="SSE", side="BUY", quantity=100, limit_price=10.0)
        self.assertEqual(intent.notional_cny(), 1000.0)


class TestGatewayRegistry(unittest.TestCase):
    def test_live_blocked(self) -> None:
        from integrations.vnpy.gateway_registry import GatewayRegistry
        from integrations.vnpy.order_intent import OrderIntent
        reg = GatewayRegistry()
        reg._gateways["XTPGateway"].enabled = True
        reg._gateways["XTPGateway"].configured = False
        reg._active = "XTPGateway"
        intent = OrderIntent.create(run_id="r", symbol="600000", exchange="SSE", side="BUY", quantity=100, limit_price=10)
        r = reg.route_intent(intent)
        self.assertEqual(r["status"], "REJECTED")

    def test_manual_confirm(self) -> None:
        from integrations.vnpy.gateway_registry import GatewayRegistry
        from integrations.vnpy.order_intent import OrderIntent
        reg = GatewayRegistry()
        reg.set_active("ManualConfirmGateway")
        intent = OrderIntent.create(run_id="r", symbol="600000", exchange="SSE", side="BUY", quantity=100, limit_price=10)
        r = reg.route_intent(intent)
        self.assertEqual(r["status"], "PENDING_MANUAL_CONFIRM")


class TestRiskBridge(unittest.TestCase):
    def test_dual_layer_reject_stale(self) -> None:
        from integrations.vnpy.risk_bridge import VnpyRiskBridge
        from integrations.vnpy.order_intent import OrderIntent
        rb = VnpyRiskBridge()
        intent = OrderIntent.create(run_id="r", symbol="600000", exchange="SSE", side="BUY", quantity=100, limit_price=10)
        d = rb.evaluate(intent, data_fresh=False, mode="PAPER_TRADING")
        self.assertFalse(d.approved)


class TestPaperBridge(unittest.TestCase):
    def test_paper_fill(self) -> None:
        from integrations.vnpy.paper_bridge import PaperBridge
        from integrations.vnpy.order_intent import OrderIntent
        with tempfile.TemporaryDirectory() as td:
            import integrations.vnpy.event_bridge as eb
            eb.EVENT_LOG = Path(td) / "e.jsonl"
            pb = PaperBridge()
            intent = OrderIntent.create(run_id="r", symbol="600000", exchange="SSE", side="BUY", quantity=100, limit_price=10)
            r = pb.submit(intent, data_fresh=True)
            self.assertIn(r["status"], {"FILLED", "REJECTED"})


class TestReconciliation(unittest.TestCase):
    def test_unknown_halt(self) -> None:
        from integrations.vnpy.reconciliation import reconcile
        r = reconcile([{"symbol": "600000", "quantity": 100}], unknown_order_ids=["o1"])
        self.assertEqual(r.action, "HALT_AND_RECONCILE")


class TestQlibProvider(unittest.TestCase):
    def test_health(self) -> None:
        from integrations.qlib.provider import CNMarketProvider
        h = CNMarketProvider().health()
        self.assertEqual(h["provider"], "CNMarketProvider")

    def test_pit_filter(self) -> None:
        from integrations.qlib.provider import CNMarketProvider
        rows = [{"trade_date": "20260620"}, {"trade_date": "20260610"}]
        out = CNMarketProvider().pit_filter(rows, "2026-06-16")
        self.assertEqual(len(out), 1)


class TestQlibWorkflow(unittest.TestCase):
    def test_baseline(self) -> None:
        from integrations.qlib.workflow import run_baseline_workflow
        with tempfile.TemporaryDirectory() as td:
            import integrations.qlib.workflow as wf
            wf.WORKFLOW_DIR = Path(td)
            r = run_baseline_workflow(as_of="2026-06-16", run_id="t1")
            self.assertFalse(r["auto_live_promotion"])
            self.assertIn(r["promotion"], {"CANDIDATE"})


class TestRuntime(unittest.TestCase):
    def test_start_stop(self) -> None:
        from services.vnpy_runtime.main import VnpyRuntimeService
        rt = VnpyRuntimeService()
        s = rt.start()
        self.assertTrue(s.get("native_vnpy") is not None)
        rt.stop()


def _api_tests() -> dict:
    try:
        from fastapi.testclient import TestClient
        from gateway.api.app import app
        from gateway.config import GatewayConfig
    except ImportError:
        return {"passed": False, "reason": "missing deps"}
    c = TestClient(app)
    h = {"X-API-Key": GatewayConfig.load().demo_api_key}
    cases = []
    r = c.get("/api/v1/quantos/status", headers=h)
    cases.append({"case": "quantos_status", "passed": r.status_code == 200})
    r = c.get("/api/v1/quantos/vnpy/doctor", headers=h)
    cases.append({"case": "vnpy_doctor", "passed": r.status_code == 200})
    r = c.post("/api/v1/quantos/vnpy/start", headers=h)
    cases.append({"case": "vnpy_start", "passed": r.status_code == 200})
    r = c.post("/api/v1/quantos/qlib/baseline", headers=h, json={"as_of": "2026-06-16"})
    cases.append({"case": "qlib_baseline", "passed": r.status_code == 200})
    r = c.post("/api/v1/quantos/paper/submit-intent", headers=h, json={
        "run_id": "t", "symbol": "600000", "exchange": "SSE", "side": "BUY", "quantity": 100, "limit_price": 10,
    })
    cases.append({"case": "paper_intent", "passed": r.status_code == 200})
    # reset kill switch after prior suites may have halted
    from gateway.risk.kill_switch import KillSwitch
    from pathlib import Path
    ks = KillSwitch()
    ks.manual_reset("test")
    passed = all(x["passed"] for x in cases)
    return {"passed": passed, "cases": cases}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestEventBridge, TestOrderIntent, TestGatewayRegistry, TestRiskBridge,
        TestPaperBridge, TestReconciliation, TestQlibProvider, TestQlibWorkflow, TestRuntime,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    api = _api_tests()
    report = {
        "unit_passed": result.wasSuccessful(),
        "unit_run": result.testsRun,
        "api_integration": api,
        "overall_passed": result.wasSuccessful() and api.get("passed", False),
    }
    (OUT / "TEST_READINESS.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
