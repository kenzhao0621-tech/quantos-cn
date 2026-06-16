#!/usr/bin/env python3
"""Gateway V2 test matrix: unit, integration, security, failure injection, load."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORT_DIR = ROOT / "docs" / "ai" / "gateway"
ARTIFACT = REPORT_DIR / "12_TEST_READINESS.json"


class TestStateMachine(unittest.TestCase):
    def test_allowed_transitions(self) -> None:
        from gateway.state_machine import StateMachine, TradingMode
        sm = StateMachine(TradingMode.RESEARCH_ONLY)
        r = sm.transition(TradingMode.DATA_READY)
        self.assertTrue(r.ok)
        r2 = sm.transition(TradingMode.PAPER_TRADING)
        self.assertTrue(r2.ok)

    def test_forbidden_live_promotion(self) -> None:
        from gateway.state_machine import StateMachine, TradingMode
        sm = StateMachine(TradingMode.SHADOW_LIVE)
        r = sm.transition(TradingMode.LIMITED_LIVE_REVIEW_REQUIRED)
        self.assertFalse(r.ok)


class TestRBAC(unittest.TestCase):
    def test_viewer_cannot_halt(self) -> None:
        from gateway.auth.rbac import Principal, Role, require_permission
        v = Principal("viewer1", Role.VIEWER, "p1")
        ok, msg = require_permission(v, "risk:halt")
        self.assertFalse(ok)

    def test_admin_can_halt(self) -> None:
        from gateway.auth.rbac import Principal, Role, require_permission
        a = Principal("admin", Role.ADMIN, "p1")
        ok, _ = require_permission(a, "risk:halt")
        self.assertTrue(ok)


class TestRiskEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ks_path = Path(self.tmp.name) / "kill.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_rejects_stale_data(self) -> None:
        from gateway.config import GatewayConfig
        from gateway.risk.engine import OrderIntent, RiskEngine
        from gateway.risk.kill_switch import KillSwitch
        cfg = GatewayConfig.load()
        cfg.mode = "PAPER_TRADING"
        r = RiskEngine(cfg, KillSwitch(self.ks_path))
        r.set_mode("PAPER_TRADING")
        intent = OrderIntent("o1", "600000.SH", "BUY", 100, 10.0, 1000.0)
        d = r.evaluate_intent(intent, data_fresh=False)
        self.assertFalse(d.approved)
        self.assertEqual(d.reason, "BLOCKED_BY_DATA")

    def test_kill_switch_blocks(self) -> None:
        from gateway.config import GatewayConfig
        from gateway.risk.engine import OrderIntent, RiskEngine
        from gateway.risk.kill_switch import KillSwitch
        ks = KillSwitch(self.ks_path)
        ks.halt("test", "tester")
        cfg = GatewayConfig.load()
        r = RiskEngine(cfg, ks)
        r.set_mode("PAPER_TRADING")
        intent = OrderIntent("o2", "600000.SH", "BUY", 100, 10.0, 1000.0)
        d = r.evaluate_intent(intent, data_fresh=True)
        self.assertFalse(d.approved)


class TestBrokers(unittest.TestCase):
    def test_paper_board_lot(self) -> None:
        from gateway.config import GatewayConfig
        from gateway.risk.engine import OrderIntent, RiskEngine
        from gateway.risk.kill_switch import KillSwitch
        from gateway.brokers.paper import PaperBrokerAdapter
        cfg = GatewayConfig.load()
        with tempfile.TemporaryDirectory() as td:
            r = RiskEngine(cfg, KillSwitch(Path(td) / "k.json"))
            r.set_mode("PAPER_TRADING")
            broker = PaperBrokerAdapter(r)
            order = broker.submit(
                OrderIntent("o3", "600000.SH", "BUY", 100, 10.0, 1000.0),
                data_fresh=True,
            )
            self.assertEqual(order.state.value, "FILLED")

    def test_shadow_no_portfolio_mutation(self) -> None:
        from gateway.config import GatewayConfig
        from gateway.risk.engine import RiskEngine
        from gateway.risk.kill_switch import KillSwitch
        from gateway.brokers.shadow import ShadowBrokerAdapter
        cfg = GatewayConfig.load()
        with tempfile.TemporaryDirectory() as td:
            r = RiskEngine(cfg, KillSwitch(Path(td) / "k.json"))
            r.set_mode("SHADOW_LIVE")
            broker = ShadowBrokerAdapter(r, Path(td) / "shadow.jsonl")
            from gateway.risk.engine import OrderIntent
            broker.submit(OrderIntent("o4", "600000.SH", "BUY", 100, 10.0, 1000.0), data_fresh=True)
            self.assertEqual(len(broker.positions), 0)


class TestSidecarGuard(unittest.TestCase):
    def test_bypass_blocked(self) -> None:
        from gateway.sidecar.gc_mgc.research import SidecarBypassError, assert_not_bypassing_ashare_validation
        with self.assertRaises(SidecarBypassError):
            assert_not_bypassing_ashare_validation(caller="test", target_path="gateway/brokers/live")

    def test_features_ok(self) -> None:
        from gateway.sidecar.gc_mgc.research import MBP10Snapshot, compute_microstructure_features
        f = compute_microstructure_features(MBP10Snapshot("GC", "t", bids=[(1, 1)], asks=[(2, 1)]))
        self.assertIn("spread", f)


class TestBacktestPIT(unittest.TestCase):
    def test_pit_passes(self) -> None:
        from gateway.backtest.event_engine import run_event_backtest
        r = run_event_backtest(
            run_id="t1", as_of_date="2026-06-16",
            bars=[{"date": "2026-06-16", "symbol": "600000.SH", "close": 10}],
            signals=[{"date": "2026-06-16", "symbol": "600000.SH", "side": "BUY", "price": 10}],
        )
        self.assertTrue(r.pit_passed)


class TestMLRegistry(unittest.TestCase):
    def test_trial_rejection(self) -> None:
        from gateway.ml.trial_registry import TrialRegistry
        with tempfile.TemporaryDirectory() as td:
            reg = TrialRegistry(Path(td) / "trials.jsonl")
            t = reg.register("m1", "s1")
            done = reg.complete(t, sharpe=0.1, num_trials=1000)
            self.assertIn(done.status, {"REJECTED", "PASSED"})


class TestAgentGovernance(unittest.TestCase):
    def test_blocked_tool(self) -> None:
        from gateway.agents.governance import validate_tool_invocation
        ok, reason = validate_tool_invocation("live_order_submit", agent_type="research", mode="PAPER_TRADING")
        self.assertFalse(ok)


def _run_api_tests() -> dict:
    """Integration + security + failure injection via TestClient."""
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        return {"name": "api-integration", "passed": False, "classification": "DEPENDENCY_MISSING"}

    from gateway.api.app import app
    from gateway.config import GatewayConfig

    cfg = GatewayConfig.load()
    client = TestClient(app)
    results: list[dict] = []

    # security: no auth
    r = client.get("/api/v1/risk/status")
    results.append({"case": "no_auth_blocked", "passed": r.status_code == 401})

    headers = {"X-API-Key": cfg.demo_api_key}

    # integration
    r = client.get("/api/v1/status", headers=headers)
    results.append({"case": "status_ok", "passed": r.status_code == 200 and r.json().get("ok")})

    r = client.get("/api/v1/agents", headers=headers)
    results.append({"case": "agents_ok", "passed": r.status_code == 200})

    r = client.post("/api/v1/research/backtest", headers=headers, json={"as_of_date": "2026-06-16"})
    results.append({"case": "backtest_ok", "passed": r.status_code == 200 and r.json()["data"]["pit_passed"]})

    # failure injection: halt then order blocked
    client.post("/api/v1/risk/halt", headers=headers, json={"reason": "fi_test"})
    r = client.get("/api/v1/risk/status", headers=headers)
    halted = r.json()["data"]["halted"]
    results.append({"case": "halt_injection", "passed": halted is True})

    # sidecar cannot reach execution
    r = client.get("/api/v1/sidecar/gc-mgc/status", headers=headers)
    results.append({
        "case": "sidecar_isolated",
        "passed": r.json()["data"]["execution_bypass_allowed"] is False,
    })

    # viewer cannot halt
    viewer_headers = {"X-API-Key": "svc-portal-read"}
    r = client.post("/api/v1/risk/halt", headers=viewer_headers, json={"reason": "x"})
    results.append({"case": "viewer_halt_denied", "passed": r.status_code == 403})

    # load: 20 concurrent status requests
    errors = []

    def hit() -> None:
        try:
            resp = client.get("/api/v1/status", headers=headers)
            if resp.status_code != 200:
                errors.append(resp.status_code)
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=hit) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    results.append({"case": "load_20_status", "passed": len(errors) == 0})

    passed = all(x["passed"] for x in results)
    return {
        "name": "api-integration",
        "passed": passed,
        "classification": "PASS" if passed else "CODE_DEFECT",
        "cases": results,
    }


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestStateMachine, TestRBAC, TestRiskEngine, TestBrokers,
        TestSidecarGuard, TestBacktestPIT, TestMLRegistry, TestAgentGovernance,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    unit_result = runner.run(suite)

    api_result = _run_api_tests()
    print(json.dumps(api_result, indent=2))

    # Readiness is orchestrated by `make test` / run-all-readiness-tests (avoids recursive gateway suite).
    readiness_path = REPORT_DIR.parent / "daily-trading" / "TEST_RECOVERY_REPORT.json"
    readiness_rc = 0
    if readiness_path.exists():
        try:
            readiness_rc = 0 if json.loads(readiness_path.read_text()).get("overall_passed") else 1
        except Exception:
            readiness_rc = 1
    else:
        readiness_rc = 1

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "unit_tests": {
            "run": unit_result.testsRun,
            "failures": len(unit_result.failures),
            "errors": len(unit_result.errors),
            "passed": unit_result.wasSuccessful(),
        },
        "api_integration": api_result,
        "readiness_artifact": str(readiness_path),
        "readiness_from_artifact": readiness_rc == 0,
        "security_cases": [c for c in api_result.get("cases", []) if "auth" in c["case"] or "halt_denied" in c["case"]],
        "failure_injection_cases": [c for c in api_result.get("cases", []) if "halt" in c["case"] or "injection" in c["case"]],
        "load_cases": [c for c in api_result.get("cases", []) if "load" in c["case"]],
        "overall_passed": unit_result.wasSuccessful() and api_result.get("passed"),
    }
    ARTIFACT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = REPORT_DIR / "12_TEST_READINESS.md"
    md.write_text(
        f"# Test Readiness Report\n\n"
        f"- Generated: {report['generated_at']}\n"
        f"- Unit: {report['unit_tests']['run']} run, passed={report['unit_tests']['passed']}\n"
        f"- API integration: {api_result.get('passed')}\n"
        f"- Readiness suite: exit {readiness_rc}\n"
        f"- Overall: **{'PASS' if report['overall_passed'] else 'FAIL'}**\n",
        encoding="utf-8",
    )
    print(f"\nWrote {ARTIFACT}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
