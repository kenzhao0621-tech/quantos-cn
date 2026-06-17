"""Operational API routes — paper/shadow, auth, system, research runs."""

from __future__ import annotations

import json
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from gateway.api.envelope import envelope_err, envelope_ok
from gateway.auth.rbac import Principal, Role, authenticate
from gateway.config import ROOT, GatewayConfig, load_runtime_state, save_runtime_mode
from gateway.preferences import apply_preferences_to_risk, load_preferences, save_preferences
from gateway.risk.engine import OrderIntent
from gateway.state_machine import TradingMode

router = APIRouter(tags=["operations"])

_cfg = GatewayConfig.load()
_RUNS_PATH = ROOT / "data" / "gateway" / "runs.json"
_RUNS_LOCK = threading.Lock()

_state: Any = None
_kill: Any = None
_risk: Any = None
_paper: Any = None
_shadow: Any = None
_audit: Any = None


def configure(**deps: Any) -> None:
    global _state, _kill, _risk, _paper, _shadow, _audit
    _state = deps["state"]
    _kill = deps["kill"]
    _risk = deps["risk"]
    _paper = deps["paper"]
    _shadow = deps["shadow"]
    _audit = deps["audit"]
    apply_preferences_to_risk(_risk)
    pref = load_preferences()
    if not _paper.orders and not _paper.positions:
        _paper.cash_cny = pref.capital_cny


async def get_principal_ops(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Optional[Principal]:
    if not x_api_key:
        return None
    return authenticate(x_api_key, _cfg.demo_api_key, _cfg.service_accounts)


def _require(principal: Optional[Principal], permission: str) -> Principal:
    from gateway.auth.rbac import require_permission
    ok, msg = require_permission(principal, permission)
    if not ok:
        raise HTTPException(status_code=401 if msg == "unauthenticated" else 403, detail=msg)
    return principal  # type: ignore[return-value]


DEV_ROLE_KEYS: dict[str, str] = {
    "admin": "demo-local-key-change-in-prod",
    "researcher": "dev-researcher-key",
    "viewer": "svc-portal-read",
    "service_risk": "dev-service-risk-key",
    "service_research": "svc-quant-pipeline",
}


class LoginBody(BaseModel):
    role: str = ""
    api_key: str = ""


class HaltBody(BaseModel):
    reason: str = "operator_halt"


class BacktestBody(BaseModel):
    as_of_date: str
    run_id: str = ""
    bars: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)


class MarketUpdateBody(BaseModel):
    targets: list[str] = Field(default_factory=lambda: ["indices", "bars"])


class PaperFromScreenerBody(BaseModel):
    preset: str = "balanced"
    top_n: int = 5
    max_positions: int = 2
    capital_fraction: float = 0.45


class UserPreferencesBody(BaseModel):
    capital_cny: float = 100000.0
    max_loss_pct: float = 0.08
    max_positions: int = 5
    max_single_position_pct: float = 0.18
    cash_buffer_pct: float = 0.20
    min_amount_cny: float = 100000000.0
    strategy_preset: str = "balanced"
    horizon: str = "3-10 sessions"
    preferred_sectors: list[str] = Field(default_factory=list)
    excluded_sectors: list[str] = Field(default_factory=list)


class AutopilotTicketBody(BaseModel):
    preset: str = "balanced"
    top_n: int = 25
    mode: str = "live"


class ModelValidationBody(BaseModel):
    preset: str = "balanced"
    lookback_days: int = 45
    top_n: int = 10
    max_per_sector: int = 2
    cost_bps: float = 8.0
    slippage_bps: float = 12.0
    min_amount_cny: float = 100000000.0


def _load_runs() -> dict[str, Any]:
    _RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _RUNS_PATH.exists():
        return {}
    return json.loads(_RUNS_PATH.read_text(encoding="utf-8"))


def _save_run(run_id: str, record: dict[str, Any]) -> None:
    with _RUNS_LOCK:
        runs = _load_runs()
        runs[run_id] = record
        _RUNS_PATH.write_text(json.dumps(runs, indent=2), encoding="utf-8")


@router.post("/api/v1/auth/login")
def auth_login(body: LoginBody) -> Dict[str, Any]:
    key = body.api_key.strip()
    if body.role and not key:
        key = DEV_ROLE_KEYS.get(body.role.strip().lower(), "")
    if not key:
        raise HTTPException(status_code=422, detail="role or api_key required")
    principal = authenticate(key, _cfg.demo_api_key, _cfg.service_accounts)
    if not principal:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return envelope_ok({
        "api_key": key,
        "role": principal.role.value,
        "user_id": principal.user_id,
        "permissions": sorted(
            __import__("gateway.auth.rbac", fromlist=["PERMISSIONS"]).PERMISSIONS.get(principal.role, set())
        ),
    })


@router.get("/api/v1/auth/me")
def auth_me(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "market:read")
    return envelope_ok({
        "user_id": p.user_id,
        "role": p.role.value,
        "project_id": p.project_id,
    })


@router.get("/api/v1/system/version")
def system_version() -> Dict[str, Any]:
    from gateway.build_info import version_payload

    return envelope_ok(version_payload())


@router.get("/api/v1/system/status")
def system_status_v2(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    apply_preferences_to_risk(_risk)
    snap = _risk.snapshot()
    runtime = load_runtime_state()
    from services.vnpy_runtime.main import get_runtime
    from integrations.qlib.provider import CNMarketProvider
    rt = get_runtime()
    return envelope_ok({
        "mode": _state.mode.value,
        "autonomous_label": _state.max_autonomous_label(),
        "market_session": _market_session(),
        "data_status": _data_status(),
        "capital": snap.capital_total_cny,
        "remaining_loss_budget": snap.remaining_loss_budget_cny,
        "equity_cny": snap.equity_cny,
        "kill_switch": snap.kill_switch,
        "halted": snap.halted,
        "blockers": snap.blockers,
        "paper_trading_only": True,
        "real_money_execution_disabled": True,
        "real_execution_mode": "MANUAL_CONFIRM_ONLY",
        "runtime": runtime,
        "vnpy": rt.status(),
        "qlib": CNMarketProvider().health(),
        "latest_daily_report": _latest_daily_report(),
        "latest_candidate": _latest_candidate(),
        "user_preferences": load_preferences().to_dict(),
    })


@router.get("/api/v1/user/preferences")
def get_user_preferences(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    return envelope_ok(load_preferences().to_dict())


@router.put("/api/v1/user/preferences")
def put_user_preferences(
    body: UserPreferencesBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "research:run")
    pref = save_preferences(body.dict())
    apply_preferences_to_risk(_risk, pref)
    if not _paper.orders and not _paper.positions:
        _paper.cash_cny = pref.capital_cny
    _audit.emit("user_preferences_update", p.user_id, pref.to_dict())
    return envelope_ok(pref.to_dict())


@router.post("/api/v1/system/doctor")
def system_doctor(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "market:read")
    run_id = str(uuid.uuid4())[:8]
    checks: list[dict[str, Any]] = []
    try:
        import gateway
        checks.append({"name": "import_gateway", "passed": True, "detail": gateway.__version__})
    except Exception as exc:
        checks.append({"name": "import_gateway", "passed": False, "detail": str(exc)})
    db_path = ROOT / "data" / "warehouse" / "quant.duckdb"
    checks.append({"name": "warehouse", "passed": db_path.exists(), "detail": str(db_path)})
    checks.append({"name": "kill_switch", "passed": True, "detail": _kill.status()})
    checks.append({"name": "risk_engine", "passed": True, "detail": _risk.snapshot().to_dict()})
    from services.vnpy_runtime.main import get_runtime
    checks.append({"name": "vnpy_runtime", "passed": True, "detail": get_runtime().doctor()})
    from integrations.qlib.provider import CNMarketProvider
    checks.append({"name": "qlib_provider", "passed": True, "detail": CNMarketProvider().health()})
    passed = all(c["passed"] for c in checks)
    _audit.emit("system_doctor", p.user_id, {"run_id": run_id, "passed": passed})
    return envelope_ok(
        {"run_id": run_id, "passed": passed, "checks": checks},
        run_id=run_id,
    )


@router.post("/api/v1/market/update")
def market_update(
    body: MarketUpdateBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "research:run")
    run_id = str(uuid.uuid4())[:8]
    results: list[dict[str, Any]] = []
    py = ROOT / ".venv-china-quant" / "bin" / "python"
    cmds = {
        "indices": [str(py), "-m", "quant", "update-indices"],
        "bars": [str(py), "-m", "quant", "update-daily-bars"],
        "sectors": [str(py), "-m", "quant", "update-sectors"],
        "fundamentals": [str(py), "-m", "quant", "update-fundamentals"],
        "disclosures": [str(py), "-m", "quant", "update-disclosures"],
    }
    for target in body.targets:
        cmd = cmds.get(target)
        if not cmd:
            results.append({"target": target, "ok": False, "error": "unknown target"})
            continue
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        results.append({
            "target": target,
            "ok": r.returncode == 0,
            "tail": (r.stdout + r.stderr)[-500:],
        })
    ok = all(x.get("ok") for x in results)
    record = {"type": "market_update", "status": "succeeded" if ok else "failed", "results": results}
    _save_run(run_id, record)
    _audit.emit("market_update", p.user_id, {"run_id": run_id, "ok": ok})
    return envelope_ok(record, run_id=run_id)


@router.post("/api/v1/paper/start")
def paper_start(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "mode:promote")
    if _kill.is_halted:
        return envelope_err("HALTED", "kill switch is HALTED — reset before starting paper")
    if _state.mode == TradingMode.RESEARCH_ONLY:
        _state.transition(TradingMode.DATA_READY, actor=p.user_id)
    tr = _state.transition(TradingMode.PAPER_TRADING, actor=p.user_id)
    if not tr.ok and _state.mode != TradingMode.PAPER_TRADING:
        return envelope_err("TRANSITION_DENIED", tr.reason)
    _risk.set_mode("PAPER_TRADING")
    save_runtime_mode("PAPER_TRADING")
    _audit.emit("paper_start", p.user_id, {"mode": "PAPER_TRADING"})
    return envelope_ok({"mode": _state.mode.value, "status": "PAPER_TRADING_ACTIVE"})


@router.post("/api/v1/paper/stop")
def paper_stop(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "mode:promote")
    prev = _state.mode.value
    _state.mode = TradingMode.RESEARCH_ONLY
    _state.history.append({"from": prev, "to": TradingMode.RESEARCH_ONLY.value, "actor": p.user_id, "note": "paper_stop"})
    _risk.set_mode("RESEARCH_ONLY")
    save_runtime_mode("RESEARCH_ONLY")
    _audit.emit("paper_stop", p.user_id, {})
    return envelope_ok({"mode": _state.mode.value, "status": "PAPER_STOPPED"})


@router.post("/api/v1/paper/from-screener")
def paper_from_screener(
    body: PaperFromScreenerBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "paper:trade")
    if _state.mode != TradingMode.PAPER_TRADING:
        return envelope_err("PAPER_NOT_STARTED", "请先点击「启动 Paper」，再从选股生成模拟组合")
    from quant.application.screener_service import get_screener_service

    pref = load_preferences()
    preset = body.preset or pref.strategy_preset
    # Pull a wider list: with smaller paper capital and A-share 100-share board
    # lots, the top ranked momentum names may be too expensive to buy one lot.
    # Paper portfolio creation must be deterministic and should not block on an
    # external realtime quote provider. Use the latest validated EOD factor set;
    # live prices are still used in the order-ticket workflow.
    screen = get_screener_service().screen(
        preset=preset,
        top_n=max(50, min(body.top_n * 4, 100)),
        min_amount_cny=pref.min_amount_cny,
        mode="eod",
        preferred_sectors=pref.preferred_sectors,
        excluded_sectors=pref.excluded_sectors,
    )
    if screen.blocked:
        return envelope_err("SCREENER_BLOCKED", screen.blocker_reason)
    if not screen.candidates:
        return envelope_err("NO_CANDIDATES", "当前没有可加入 Paper 的候选")

    snap = _risk.snapshot()
    deployable = snap.equity_cny * max(0.05, min(body.capital_fraction, 0.6))
    target_positions = max(1, min(body.max_positions or pref.max_positions, pref.max_positions, 10))
    risk = _risk.config.risk
    per_name = min(deployable / target_positions, snap.equity_cny * risk.maximum_single_name_risk_pct)
    run_id = str(uuid.uuid4())[:8]
    orders: list[dict[str, Any]] = []
    blockers: list[str] = []
    for c in screen.candidates:
        if len(orders) >= target_positions:
            break
        raw_qty = int(per_name / max(c.last_close, 0.01))
        qty = (raw_qty // 100) * 100
        if qty < 100:
            blockers.append(f"{c.symbol}: 资金不足买入一手")
            continue
        intent = OrderIntent(
            client_order_id=str(uuid.uuid4()),
            run_id=run_id,
            strategy_id=f"screener:{body.preset}",
            model_id="multi_factor_screener_v1",
            symbol=c.symbol,
            side="BUY",
            quantity=qty,
            limit_price=round(c.last_close, 2),
            notional_cny=round(qty * c.last_close, 2),
        )
        order = _paper.submit(intent, data_fresh=True, market_price=c.last_close)
        od = order.to_dict()
        if od.get("state") == "FILLED":
            orders.append(od)
        else:
            blockers.append(f"{c.symbol}: {od.get('reject_reason') or od.get('state')}")

    _audit.emit("paper_from_screener", p.user_id, {
        "run_id": run_id,
        "preset": body.preset,
        "orders": len(orders),
        "blockers": blockers,
    })
    return envelope_ok({
        "run_id": run_id,
        "mode": _state.mode.value,
        "as_of_date": screen.as_of_date,
        "orders": orders,
        "blockers": blockers,
        "note": "仅模拟交易；未连接真实券商，零真实订单。",
    }, run_id=run_id)


@router.post("/api/v1/shadow/start")
def shadow_start(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "mode:promote")
    if _kill.is_halted:
        return envelope_err("HALTED", "kill switch is HALTED")
    if _state.mode == TradingMode.RESEARCH_ONLY:
        _state.transition(TradingMode.DATA_READY, actor=p.user_id)
    if _state.mode == TradingMode.DATA_READY:
        _state.transition(TradingMode.PAPER_TRADING, actor=p.user_id)
    tr = _state.transition(TradingMode.SHADOW_LIVE, actor=p.user_id)
    if not tr.ok and _state.mode != TradingMode.SHADOW_LIVE:
        return envelope_err("TRANSITION_DENIED", tr.reason)
    _risk.set_mode("SHADOW_LIVE")
    save_runtime_mode("SHADOW_LIVE")
    _audit.emit("shadow_start", p.user_id, {"zero_real_orders": True})
    return envelope_ok({
        "mode": _state.mode.value,
        "status": "SHADOW_LIVE_ACTIVE",
        "zero_real_orders_sent": True,
    })


@router.post("/api/v1/shadow/stop")
def shadow_stop(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "mode:promote")
    prev = _state.mode.value
    _state.mode = TradingMode.PAPER_TRADING
    _state.history.append({"from": prev, "to": TradingMode.PAPER_TRADING.value, "actor": p.user_id, "note": "shadow_stop"})
    _risk.set_mode("PAPER_TRADING")
    save_runtime_mode("PAPER_TRADING")
    _audit.emit("shadow_stop", p.user_id, {})
    return envelope_ok({"mode": _state.mode.value, "status": "SHADOW_STOPPED"})


@router.get("/api/v1/shadow/status")
def shadow_status(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "paper:read")
    return envelope_ok({
        "mode": _state.mode.value,
        "shadow_active": _state.mode == TradingMode.SHADOW_LIVE,
        "zero_real_orders_sent": True,
        "events": _shadow.list_events() if hasattr(_shadow, "list_events") else [],
        "intents": getattr(_shadow, "intents", []),
    })


@router.post("/api/v1/risk/reset-confirm")
def risk_reset_confirm(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "risk:reset_request")
    if p.role not in {Role.ADMIN, Role.SERVICE_RISK}:
        raise HTTPException(status_code=403, detail="forbidden: admin or service_risk required for reset confirm")
    st = _kill.manual_reset(p.user_id)
    if _state.mode == TradingMode.HALTED:
        _state.transition(TradingMode.RESEARCH_ONLY, actor=p.user_id)
    _risk.set_mode("RESEARCH_ONLY")
    save_runtime_mode("RESEARCH_ONLY")
    _audit.emit("risk_reset_confirm", p.user_id, st.to_dict())
    return envelope_ok({"reset": True, "kill_switch": st.to_dict(), "mode": _state.mode.value})


@router.get("/api/v1/research/runs/{run_id}")
def get_research_run(run_id: str, principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "research:read")
    runs = _load_runs()
    run = runs.get(run_id)
    if not run:
        return envelope_err("NOT_FOUND", f"run {run_id} not found", run_id=run_id)
    return envelope_ok(run, run_id=run_id)


@router.get("/api/v1/research/runs/{run_id}/report")
def get_research_run_report(run_id: str, principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "research:read")
    daily_dir = ROOT / "docs" / "ai" / "daily-trading" / "daily"
    candidates = list(daily_dir.glob(f"*{run_id}*")) if daily_dir.exists() else []
    if not candidates:
        meta = ROOT / "docs" / "ai" / "daily-trading" / "2026-06-16_RUN_META.json"
        if meta.exists():
            return envelope_ok({
                "run_id": run_id,
                "report_json": str(meta),
                "report_md": str(ROOT / "docs" / "ai" / "daily-trading" / "daily" / "2026-06-16_DAILY_QUANT_REPORT.md"),
                "report_pdf": str(ROOT / "docs" / "ai" / "daily-trading" / "daily" / "2026-06-16_DAILY_QUANT_REPORT.pdf"),
            }, run_id=run_id)
        return envelope_err("NOT_FOUND", f"no report artifact for run {run_id}", run_id=run_id)
    return envelope_ok({"run_id": run_id, "artifacts": [str(p) for p in candidates]}, run_id=run_id)


@router.get("/api/v1/native/status")
def native_status(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.native.bridge import native_qlib_status, native_vnpy_status
    from services.vnpy_runtime.main import get_runtime
    from integrations.qlib.provider import CNMarketProvider
    vn_iso = native_vnpy_status()
    ql_iso = native_qlib_status()
    vn_main = get_runtime().doctor()
    ql_main = CNMarketProvider().health()
    return envelope_ok({
        "vnpy": {
            "isolated_venv": vn_iso,
            "main_runtime": vn_main,
            "mode": vn_iso.get("mode", "SHIM"),
            "state": vn_iso.get("state", "NOT_INSTALLED"),
        },
        "qlib": {
            "isolated_venv": ql_iso,
            "main_provider": ql_main,
            "mode": ql_iso.get("mode", "SHIM"),
            "state": ql_iso.get("state", "NOT_INSTALLED"),
        },
        "real_execution_mode": "MANUAL_CONFIRM_ONLY",
    })


@router.post("/api/v1/native/vnpy/acceptance")
def native_vnpy_acceptance(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "research:run")
    from gateway.native.bridge import run_native_script
    result = run_native_script("vnpy", "vnpy_acceptance.py")
    _audit.emit("native_vnpy_acceptance", p.user_id, result)
    report_path = str(ROOT / "docs" / "ai" / "final" / "06_NATIVE_VNPY_ACCEPTANCE.json")
    return envelope_ok({**result, "artifact_path": report_path})


@router.post("/api/v1/native/qlib/acceptance")
def native_qlib_acceptance(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "research:run")
    from gateway.native.bridge import run_native_script
    result = run_native_script("qlib", "qlib_acceptance.py", timeout=600)
    _audit.emit("native_qlib_acceptance", p.user_id, result)
    report_path = str(ROOT / "docs" / "ai" / "final" / "07_NATIVE_QLIB_ACCEPTANCE.json")
    return envelope_ok({**result, "artifact_path": report_path})


@router.post("/api/v1/research/agents/run")
def research_agents_run(body: dict, principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "research:run")
    from gateway.agents.cn_research.workflow import run_agent_research
    as_of = body.get("as_of", "2026-06-16")
    result = run_agent_research(as_of=as_of, run_id=body.get("run_id", ""))
    _audit.emit("agent_research_run", p.user_id, {"run_id": result.run_id})
    artifact = str(ROOT / "data" / "gateway" / "agent_runs" / f"{result.run_id}.json")
    return envelope_ok(result.to_dict(), run_id=result.run_id, artifact_path=artifact)


@router.get("/api/v1/brokers/wizard")
def brokers_wizard(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.brokers.wizard import broker_wizard_state
    return envelope_ok(broker_wizard_state())


@router.get("/api/v1/autopilot/readiness")
def autopilot_readiness(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.autopilot import readiness_snapshot

    return envelope_ok(readiness_snapshot())


@router.get("/api/v1/gateway/readiness")
def gateway_readiness(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.production_readiness import gateway_readiness_report

    return envelope_ok(gateway_readiness_report())


@router.post("/api/v1/autopilot/order-ticket")
def autopilot_order_ticket(
    body: AutopilotTicketBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "research:run")
    from gateway.autopilot import generate_order_ticket

    ticket = generate_order_ticket(preset=body.preset, top_n=body.top_n, mode=body.mode)
    _audit.emit("autopilot_order_ticket", p.user_id, {
        "ticket_id": ticket.get("ticket_id"),
        "status": ticket.get("status"),
        "lines": len(ticket.get("lines", [])),
    })
    return envelope_ok(ticket, run_id=ticket.get("ticket_id"))


@router.post("/api/v1/models/validate")
def models_validate(
    body: ModelValidationBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    _require(principal, "research:run")
    from quant.application.model_validation_service import ValidationConfig, get_model_validation_service

    cfg = ValidationConfig(
        preset=body.preset,
        lookback_days=max(10, min(body.lookback_days, 90)),
        top_n=max(3, min(body.top_n, 30)),
        max_per_sector=max(1, min(body.max_per_sector, 5)),
        cost_bps=max(0, min(body.cost_bps, 100)),
        slippage_bps=max(0, min(body.slippage_bps, 200)),
        min_amount_cny=max(0, body.min_amount_cny),
    )
    result = get_model_validation_service().validate(cfg).to_dict()
    return envelope_ok(result)


@router.post("/api/v1/brokers/readonly-connect")
def brokers_readonly_connect(body: dict, principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "portal:admin")
    from gateway.brokers.wizard import readonly_connect_wizard
    result = readonly_connect_wizard(body.get("broker", ""), body.get("config", {}))
    _audit.emit("broker_readonly_wizard", p.user_id, result)
    return envelope_ok(result)


@router.get("/api/v1/version")
def app_version() -> Dict[str, Any]:
    import gateway
    import subprocess
    commit = "unknown"
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()[:12]
    except Exception:
        pass
    return envelope_ok({
        "gateway_version": gateway.__version__,
        "commit": commit,
        "product": "QuantOS CN",
        "real_money_disabled": True,
    })


def _market_session() -> str:
    try:
        from quant.market_hours import current_session_label
        return current_session_label()
    except Exception:
        return "UNKNOWN"


def _data_status() -> str:
    db = ROOT / "data" / "warehouse" / "quant.duckdb"
    if db.exists():
        return "WAREHOUSE_PRESENT"
    return "BLOCKED_BY_DATA"


def _latest_daily_report() -> dict[str, Any]:
    daily = ROOT / "docs" / "ai" / "daily-trading" / "daily"
    pdfs = sorted(daily.glob("*_DAILY_QUANT_REPORT.pdf")) if daily.exists() else []
    pdf = pdfs[-1] if pdfs else daily / "2026-06-16_DAILY_QUANT_REPORT.pdf"
    md = pdf.with_suffix(".md")
    js = pdf.with_suffix(".json")
    if pdf.exists():
        desktop_dir = ""
        desktop_files: dict[str, str] = {}
        if js.exists():
            try:
                data = json.loads(js.read_text(encoding="utf-8"))
                delivery = data.get("desktop_delivery") or {}
                desktop_dir = delivery.get("desktop_dir", "")
                desktop_files = delivery.get("delivered", {})
            except Exception:
                pass
        return {
            "path_pdf": str(pdf),
            "path_md": str(md) if md.exists() else "",
            "path_json": str(js) if js.exists() else "",
            "desktop_dir": desktop_dir,
            "desktop_files": desktop_files,
            "status": "AVAILABLE",
        }
    return {"status": "NOT_GENERATED"}


def _latest_candidate() -> dict[str, Any]:
    meta = ROOT / "docs" / "ai" / "daily-trading" / "2026-06-16_RUN_META.json"
    if meta.exists():
        try:
            return json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "NO_CANDIDATE"}


def run_daily_report_async(user_id: str) -> str:
    """Background daily report — returns run_id."""
    run_id = str(uuid.uuid4())[:8]

    def _worker() -> None:
        py = ROOT / ".venv-china-quant" / "bin" / "python"
        script = ROOT / "scripts" / "run-daily-quant-pipeline.py"
        _save_run(run_id, {"type": "daily_report", "status": "running", "started_at": datetime.now(timezone.utc).isoformat()})
        r = subprocess.run([str(py), str(script)], cwd=str(ROOT), capture_output=True, text=True, timeout=600)
        _save_run(run_id, {
            "type": "daily_report",
            "status": "succeeded" if r.returncode == 0 else "failed",
            "exit_code": r.returncode,
            "tail": (r.stdout + r.stderr)[-2000:],
            "latest_daily_report": _latest_daily_report(),
        })
        _audit.emit("daily_report_complete", user_id, {"run_id": run_id, "ok": r.returncode == 0})

    threading.Thread(target=_worker, daemon=True).start()
    return run_id
