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
    "investor": "dev-investor-key",
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


class BrokerConfigBody(BaseModel):
    active_broker: str = "eastmoney_manual"
    account_id: str = ""
    readonly: bool = False
    sidecar_url: str = ""
    sidecar_api_key: str = ""
    auto_trade_via_sidecar: bool = False
    qmt_order_dir: str = ""


class ConnectFlowBody(BaseModel):
    broker_id: str = ""
    open_login: bool = True
    sync_watchlist: bool = True
    wait_seconds: int = 120


class LoginAssistBody(BaseModel):
    broker_id: str = ""
    wait_seconds: int = 180
    force: bool = False


class BrokerLaunchBody(BaseModel):
    broker_id: str = ""
    target: str = "trade_login"
    symbol: str = ""
    name: str = ""


class LiveOrderBody(BaseModel):
    symbol: str
    name: str = ""
    side: str = "BUY"
    quantity: int = 100
    limit_price: float = 0.0
    user_confirmed: bool = False
    unattended: bool = False


class ExecuteAutoBody(BaseModel):
    symbol: str
    name: str = ""
    side: str = "BUY"
    quantity: int = 100
    limit_price: float = 0.0


class WatchlistMutateBody(BaseModel):
    symbol: str
    name: str = ""
    notes: str = ""


class LocalConsentBody(BaseModel):
    granted: bool = True


class LiveGatesBody(BaseModel):
    execution_level: int = 2
    real_money_enabled: bool = False
    user_confirmed_risk: bool = False
    legal_review_passed: bool = False
    unattended_auto_enabled: bool = False
    browser_auto_submit: bool = False
    max_single_order_cny: float = 2000.0
    max_daily_notional_cny: float = 5000.0


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


@router.get("/api/v1/onboarding/beginner")
def onboarding_beginner(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from quant.learning.outcome_tracker import compute_learning_summary

    learning = compute_learning_summary()
    return envelope_ok({
        "title": "新手入门量化投资",
        "audience": "A股新投资者",
        "steps": [
            {"id": 1, "title": "更新数据", "action": "market-update", "hint": "市场中心 → 同步数据"},
            {"id": 2, "title": "智能选股", "action": "screener-run", "hint": "设置资金（如5000元）→ 运行选股"},
            {"id": 3, "title": "模拟练习", "action": "paper-start", "hint": "先用模拟盘验证，零真实资金"},
            {"id": 4, "title": "连接券商", "action": "broker-connect", "hint": "登录一次 → 系统帮你预填订单"},
            {"id": 5, "title": "人工确认下单", "action": "broker-assist", "hint": "在券商官方 App 点击确认，系统不自动扣款"},
        ],
        "disclaimer": {
            "not_investment_advice": True,
            "no_auto_real_orders": True,
            "no_password_storage": True,
            "t_plus_one": True,
            "model_may_fail": True,
        },
        "daily_learning": learning,
        "help_doc": "/docs/USER_GUIDE.md",
    })


@router.get("/api/v1/deployment/eligibility")
def deployment_eligibility(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.deployment.eligibility import compute_deployment_eligibility

    return envelope_ok(compute_deployment_eligibility())


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
    from gateway.deployment.eligibility import compute_deployment_eligibility

    rt = get_runtime()
    deploy = compute_deployment_eligibility()
    return envelope_ok({
        "mode": _state.mode.value,
        "deployment_eligibility": deploy["deployment_eligibility"],
        "deployment_gates": deploy.get("gates", {}),
        "deployment_blockers": deploy.get("blockers", []),
        "autonomous_label": _state.max_autonomous_label(),
        "market_session": _market_session(),
        "data_status": _data_status(),
        "data_freshness": _data_freshness(),
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


@router.get("/api/v1/brokers/ecosystem")
def brokers_ecosystem(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.brokers.cn_broker_registry import CN_BROKER_ECOSYSTEM, BROWSER_BROKER_IDS, portal_links

    brokers = []
    for bid, spec in CN_BROKER_ECOSYSTEM.items():
        brokers.append({
            "broker_id": bid,
            "label": spec.get("label", bid),
            "handoff": spec.get("handoff", ""),
            "ecosystem": spec.get("ecosystem", []),
            "urls": spec.get("urls", {}),
            "browser_capable": bid in BROWSER_BROKER_IDS,
            "order_hint": spec.get("order_hint", ""),
            "watchlist_hint": spec.get("watchlist_hint", ""),
            "notes": spec.get("notes", ""),
        })
    return envelope_ok({
        "brokers": brokers,
        "portal_links": portal_links(),
        "default_broker": "eastmoney_manual",
    })


@router.get("/api/v1/brokers/config")
def brokers_config_get(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.brokers.connection_manager import load_broker_config

    return envelope_ok(load_broker_config().to_dict())


@router.put("/api/v1/brokers/config")
def brokers_config_put(
    body: BrokerConfigBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "broker:connect")
    from gateway.brokers.connection_manager import save_broker_config

    cfg = save_broker_config(body.model_dump())
    _audit.emit("broker_config_save", p.user_id, {"active_broker": cfg.active_broker})
    return envelope_ok(cfg.to_dict())


@router.post("/api/v1/brokers/connect-flow")
def brokers_connect_flow(
    body: ConnectFlowBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "broker:connect")
    from gateway.brokers.broker_autopilot import run_connect_flow

    result = run_connect_flow(
        broker_id=body.broker_id or None,
        user_id=p.user_id,
        open_login=body.open_login,
        sync_watchlist=body.sync_watchlist,
        wait_seconds=body.wait_seconds,
    )
    _audit.emit("broker_connect_flow", p.user_id, {
        "broker_id": result.get("broker_id"),
        "ready": result.get("ready_for_trade"),
    })
    return envelope_ok(result)


@router.post("/api/v1/brokers/login-assist")
def brokers_login_assist(
    body: LoginAssistBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "broker:connect")
    from gateway.brokers.connection_manager import load_broker_config, save_broker_config
    from gateway.brokers.playwright_assist import run_login_assist, session_path

    cfg = load_broker_config()
    bid = body.broker_id or cfg.active_broker
    if body.force and session_path(bid).exists():
        session_path(bid).unlink(missing_ok=True)
    save_broker_config({"active_broker": bid, "readonly": False})
    result = run_login_assist(bid, wait_seconds=body.wait_seconds)
    _audit.emit("broker_login_assist", p.user_id, {"broker_id": bid, "logged_in": result.get("logged_in_detected")})
    return envelope_ok(result)


@router.post("/api/v1/brokers/auto-session")
def brokers_auto_session(
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "broker:connect")
    from gateway.brokers.broker_autopilot import run_post_login_automation

    result = run_post_login_automation(user_id=p.user_id, export_fills=True)
    _audit.emit("broker_auto_session", p.user_id, {"actions": len(result.get("actions", []))})
    return envelope_ok(result)


@router.post("/api/v1/brokers/launch")
def brokers_launch(
    body: BrokerLaunchBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    _require(principal, "broker:connect")
    from gateway.brokers.broker_launcher import launch_cn_broker
    from gateway.brokers.connection_manager import load_broker_config

    cfg = load_broker_config()
    bid = body.broker_id or cfg.active_broker
    result = launch_cn_broker(bid, symbol=body.symbol, name=body.name, target=body.target)
    return envelope_ok(result)


@router.get("/api/v1/brokers/session")
def brokers_session(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.brokers.unified_bridge import broker_session_status

    return envelope_ok(broker_session_status())


@router.get("/api/v1/brokers/acceptance")
def brokers_acceptance(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.brokers.acceptance import run_broker_acceptance

    return envelope_ok(run_broker_acceptance())


@router.get("/api/v1/brokers/monitor")
def brokers_monitor(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.brokers.connection_manager import load_broker_config
    from gateway.brokers.playwright_assist import session_status
    from gateway.brokers.unified_bridge import broker_session_status
    from gateway.live_trading.gates import load_gates

    cfg = load_broker_config()
    gates = load_gates()
    return envelope_ok({
        "active_broker": cfg.active_broker,
        "gates": gates.to_dict(),
        "browser_session": session_status(cfg.active_broker),
        "session": broker_session_status(cfg),
    })


@router.get("/api/v1/live-trading/gates")
def live_gates_get(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.live_trading.gates import load_gates

    return envelope_ok(load_gates().to_dict())


@router.put("/api/v1/live-trading/gates")
def live_gates_put(
    body: LiveGatesBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "portal:admin")
    from gateway.live_trading.gates import save_gates

    gates = save_gates(body.model_dump())
    _audit.emit("live_gates_update", p.user_id, gates.to_dict())
    return envelope_ok(gates.to_dict())


@router.post("/api/v1/brokers/live-order")
def brokers_live_order(
    body: LiveOrderBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "broker:assist")
    from gateway.brokers.unified_bridge import place_real_order

    result = place_real_order(
        symbol=body.symbol,
        name=body.name,
        side=body.side,
        quantity=body.quantity,
        limit_price=body.limit_price,
        user_confirmed=body.user_confirmed,
        user_id=p.user_id,
        unattended=body.unattended,
    )
    _audit.emit("broker_live_order", p.user_id, {
        "symbol": body.symbol,
        "ok": result.get("ok"),
        "mode": (result.get("handoff") or {}).get("mode"),
    })
    if result.get("ok"):
        return envelope_ok(result)
    return envelope_err(
        result.get("error", {}).get("code", "LIVE_ORDER_FAILED"),
        result.get("error", {}).get("message", result.get("user_action", "下单失败")),
        blockers=result.get("blockers"),
        gates=result.get("gates"),
    )


@router.get("/api/v1/watchlist")
def watchlist_list(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "market:read")
    from gateway.screener.watchlist import list_watchlist

    return envelope_ok({"items": list_watchlist(p.user_id)})


@router.post("/api/v1/watchlist")
def watchlist_add(
    body: WatchlistMutateBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "market:read")
    from gateway.screener.watchlist import add_to_watchlist

    item = add_to_watchlist(p.user_id, symbol=body.symbol, name=body.name, notes=body.notes)
    return envelope_ok(item)


@router.delete("/api/v1/watchlist/{symbol}")
def watchlist_remove(
    symbol: str,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "market:read")
    from gateway.screener.watchlist import remove_from_watchlist

    removed = remove_from_watchlist(p.user_id, symbol)
    return envelope_ok({"removed": removed, "symbol": symbol})


@router.post("/api/v1/watchlist/sync")
def watchlist_sync(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "broker:connect")
    from gateway.brokers.unified_bridge import sync_watchlist_to_broker
    from gateway.screener.watchlist import list_watchlist

    items = list_watchlist(p.user_id)
    result = sync_watchlist_to_broker(p.user_id, items)
    _audit.emit("watchlist_sync", p.user_id, {"count": len(items), "ok": result.get("ok")})
    return envelope_ok(result)


@router.get("/api/v1/brokers/execution-paths")
def brokers_execution_paths(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.brokers.execution_router import list_execution_paths

    return envelope_ok({"paths": list_execution_paths(), "platform": __import__("platform").system()})


@router.post("/api/v1/brokers/execute-auto")
def brokers_execute_auto(
    body: ExecuteAutoBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "mode:promote")
    from gateway.brokers.execution_router import execute_order

    result = execute_order(
        symbol=body.symbol,
        name=body.name,
        side=body.side,
        quantity=body.quantity,
        limit_price=body.limit_price,
        user_id=p.user_id,
        unattended=True,
        source="execute_auto",
    )
    _audit.emit("broker_execute_auto", p.user_id, {
        "symbol": body.symbol,
        "ok": result.get("ok"),
        "winning_path": result.get("winning_path"),
    })
    if result.get("ok"):
        return envelope_ok(result)
    return envelope_err(
        result.get("error", {}).get("code", "EXECUTE_AUTO_FAILED"),
        result.get("error", {}).get("message", result.get("user_action", "无人值守执行失败")),
        paths_tried=result.get("paths_tried"),
    )


@router.post("/api/v1/brokers/local-consent")
def brokers_local_consent(
    body: LocalConsentBody,
    principal: Optional[Principal] = Depends(get_principal_ops),
) -> Dict[str, Any]:
    p = _require(principal, "broker:connect")
    from gateway.brokers.local_auth import save_consent

    return envelope_ok(save_consent(p.user_id, granted=body.granted))


@router.post("/api/v1/brokers/export-fills")
def brokers_export_fills(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    p = _require(principal, "broker:connect")
    from gateway.brokers.connection_manager import load_broker_config
    from gateway.brokers.playwright_assist import auto_export_fills

    cfg = load_broker_config()
    result = auto_export_fills(cfg.active_broker)
    _audit.emit("broker_export_fills", p.user_id, {"imported": result.get("fills_imported", 0)})
    return envelope_ok(result)


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
    p = _require(principal, "broker:connect")
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


def _data_freshness() -> dict[str, Any]:
    from gateway.market_status import get_market_status_summary

    return get_market_status_summary()


@router.get("/api/v1/system/setup-checklist")
def setup_checklist(principal: Optional[Principal] = Depends(get_principal_ops)) -> Dict[str, Any]:
    """Onboarding checklist and artifact paths for the portal 配置中心."""
    _require(principal, "market:read")
    from gateway.brokers.connection_manager import CONFIG_PATH, load_broker_config
    from gateway.env_loader import tushare_configured

    summary = _data_freshness()
    wh = summary.get("warehouse") or {}
    live = summary.get("live") or {}
    cfg = load_broker_config()
    broker_saved = bool(cfg.active_broker and cfg.active_broker != "none")
    ticket_dir = ROOT / "data" / "gateway" / "order_tickets"
    tickets = list(ticket_dir.glob("*.json")) if ticket_dir.exists() else []
    daily_dir = ROOT / "docs" / "ai" / "daily-trading" / "daily"
    pdfs = sorted(daily_dir.glob("*_DAILY_QUANT_REPORT.pdf")) if daily_dir.exists() else []

    steps = [
        {
            "id": "env",
            "title": "配置 Tushare Token",
            "done": tushare_configured(),
            "hint": "复制 .env.example 为 .env 并填入 TUSHARE_TOKEN，然后重启 make app",
            "action": "show-env",
        },
        {
            "id": "data",
            "title": "同步市场数据（日线 + 指数 + 实时）",
            "done": bool(wh.get("daily_latest")) and not summary.get("needs_index_sync") and live.get("ok"),
            "hint": summary.get("labels", {}).get("pill", "点击「同步全部数据」"),
            "action": "market-sync-all",
        },
        {
            "id": "broker",
            "title": "配置券商连接（只读 / 导出）",
            "done": broker_saved,
            "hint": "在「券商」页选择 Eastmoney 或 QMT 并测试连接",
            "action": "goto-brokers",
        },
        {
            "id": "screener",
            "title": "运行智能选股",
            "done": bool(wh.get("daily_latest")),
            "hint": "选股基于 EOD 因子；实时模式需 live 快照可用",
            "action": "goto-screener",
        },
        {
            "id": "ticket",
            "title": "生成订单票据（人工确认）",
            "done": len(tickets) > 0,
            "hint": "Autopilot 生成票据 → 券商官方 App 手动确认 → 导入成交 CSV 对账",
            "action": "goto-paper",
        },
    ]
    complete = sum(1 for s in steps if s["done"])

    return envelope_ok({
        "score": {"complete": complete, "total": len(steps)},
        "steps": steps,
        "market_status": summary,
        "artifacts": {
            "env_example": str(ROOT / ".env.example"),
            "env_file": str(ROOT / ".env"),
            "warehouse": str(ROOT / "data" / "warehouse" / "quant.duckdb"),
            "live_snapshot": str(ROOT / "data" / "gateway" / "live_snapshot.json"),
            "order_tickets_dir": str(ticket_dir),
            "broker_config": str(CONFIG_PATH),
            "daily_report_pdf": str(pdfs[-1]) if pdfs else str(daily_dir / "2026-06-16_DAILY_QUANT_REPORT.pdf"),
            "user_guide": str(ROOT / "docs" / "USER_GUIDE.md"),
        },
    })


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
