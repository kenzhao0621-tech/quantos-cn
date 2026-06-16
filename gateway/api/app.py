"""Gateway FastAPI application."""

import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from gateway import __version__, PAPER_TRADING_ONLY, REAL_MONEY_EXECUTION_DISABLED
from gateway.agents.catalog import AgentCatalog
from gateway.agents.governance import governance_report, validate_tool_invocation
from gateway.api.envelope import envelope_err, envelope_ok
from gateway.auth.rbac import Principal, authenticate, require_permission
from gateway.backtest.event_engine import run_event_backtest
from gateway.brokers.paper import PaperBrokerAdapter
from gateway.brokers.shadow import ShadowBrokerAdapter
from gateway.config import GatewayConfig, ROOT, load_runtime_state
from gateway.ml.trial_registry import TrialRegistry
from gateway.observability.audit import AuditLogger, TraceContext
from gateway.portfolio.constructor import construct_portfolio
from gateway.risk.engine import OrderIntent, RiskEngine
from gateway.risk.kill_switch import KillSwitch
from gateway.sidecar.gc_mgc.research import (
    MBP10Snapshot,
    assert_not_bypassing_ashare_validation,
    compute_microstructure_features,
    sidecar_research_status,
)
from gateway.state_machine import StateMachine, TradingMode

app = FastAPI(title="China A-share Gateway", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_cfg = GatewayConfig.load()
_kill = KillSwitch()
_risk = RiskEngine(_cfg, _kill)
_paper = PaperBrokerAdapter(_risk)
_shadow = ShadowBrokerAdapter(_risk)
_state = StateMachine(TradingMode(_cfg.mode))
_catalog = AgentCatalog()
_audit = AuditLogger()
_trials = TrialRegistry()
_tasks: dict[str, dict[str, Any]] = {}


def _trace(request: Request, x_request_id: Optional[str], x_trace_id: Optional[str], principal: Principal) -> TraceContext:
    return TraceContext(
        trace_id=x_trace_id or str(uuid.uuid4()),
        request_id=x_request_id or str(uuid.uuid4()),
        user_id=principal.user_id,
        project_id=principal.project_id,
    )


async def get_principal(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Optional[Principal]:
    if not x_api_key:
        return None
    return authenticate(x_api_key, _cfg.demo_api_key, _cfg.service_accounts)


def _require(principal: Optional[Principal], permission: str) -> Principal:
    ok, msg = require_permission(principal, permission)
    if not ok:
        raise HTTPException(status_code=401 if msg == "unauthenticated" else 403, detail=msg)
    return principal  # type: ignore[return-value]


class InvokeBody(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    run_id: str = ""
    tool: str = ""


class TaskBody(BaseModel):
    task_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    run_id: str = ""


class HaltBody(BaseModel):
    reason: str = "operator_halt"


class BacktestBody(BaseModel):
    as_of_date: str
    run_id: str = ""
    bars: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/ready")
def ready() -> Dict[str, Any]:
    return {
        "status": "ready",
        "mode": _state.mode.value,
        "paper_trading_only": PAPER_TRADING_ONLY,
        "real_money_execution_disabled": REAL_MONEY_EXECUTION_DISABLED,
    }


@app.get("/api/v1/market/status")
def market_status(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    runtime = load_runtime_state()
    return envelope_ok({
        "mode": _state.mode.value,
        "session": "CLOSED",
        "paper_trading_only": PAPER_TRADING_ONLY,
        "runtime": runtime,
    }, request_id=str(uuid.uuid4()))


@app.get("/api/v1/market/providers")
def market_providers(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    return envelope_ok({
        "providers": ["akshare_sina", "baostock", "tushare", "rqdata", "qmt"],
        "primary_market": "CN_A_SHARE",
    })


@app.get("/api/v1/market/snapshot")
def market_snapshot(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    try:
        from quant.market_data_fabric import fetch_spot_snapshot
        snap = fetch_spot_snapshot()
        return envelope_ok(snap if isinstance(snap, dict) else {"raw": str(snap)})
    except Exception as exc:
        return envelope_ok({"status": "demo_fixture", "freshness": "END_OF_DAY", "error": str(exc)[:200]})


@app.get("/api/v1/market/indices")
def market_indices(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    idx_path = ROOT / "data" / "indices"
    indices = []
    if idx_path.exists():
        import json
        for f in idx_path.glob("*.json"):
            try:
                indices.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
    return envelope_ok({"indices": indices[:10]})


@app.get("/api/v1/market/sectors")
def market_sectors(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    return envelope_ok({"sectors": [], "source": "warehouse"})


@app.post("/api/v1/agents/{agent_id}/invoke")
def invoke_agent(
    agent_id: str,
    body: InvokeBody,
    request: Request,
    principal: Optional[Principal] = Depends(get_principal),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
    x_trace_id: Optional[str] = Header(default=None, alias="X-Trace-Id"),
) -> Dict[str, Any]:
    p = _require(principal, "agents:invoke")
    trace = _trace(request, x_request_id, x_trace_id, p)
    ok, reason = _catalog.can_invoke(agent_id, _state.mode.value)
    if not ok:
        return envelope_err("AGENT_FORBIDDEN", reason, trace_id=trace.trace_id)
    if body.tool:
        agent = _catalog.get(agent_id)
        tool_ok, tool_reason = validate_tool_invocation(
            body.tool,
            agent_type=agent.type if agent else "research",
            mode=_state.mode.value,
            sidecar=bool(agent and agent.isolated),
        )
        if not tool_ok:
            return envelope_err("TOOL_BLOCKED", tool_reason, trace_id=trace.trace_id)
    route = _catalog.route_model(agent_id)
    _audit.emit("agent_invoke", p.user_id, {"agent_id": agent_id, "tool": body.tool}, trace)
    return envelope_ok({"agent_id": agent_id, "route": route, "output": {"status": "accepted"}}, trace_id=trace.trace_id)


@app.post("/api/v1/tasks")
def create_task(body: TaskBody, principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    p = _require(principal, "tasks:create")
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {"task_type": body.task_type, "payload": body.payload, "status": "QUEUED", "run_id": body.run_id}
    _audit.emit("task_create", p.user_id, {"task_id": task_id, "type": body.task_type})
    return envelope_ok({"task_id": task_id, "status": "QUEUED"})


@app.get("/api/v1/tasks/{task_id}")
def get_task(task_id: str, principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "tasks:read")
    task = _tasks.get(task_id)
    if not task:
        return envelope_err("NOT_FOUND", f"task {task_id} not found")
    return envelope_ok(task)


@app.post("/api/v1/research/daily-run")
def research_daily_run(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    p = _require(principal, "research:run")
    run_id = str(uuid.uuid4())[:8]
    _audit.emit("daily_run", p.user_id, {"run_id": run_id})
    return envelope_ok({"run_id": run_id, "status": "QUEUED", "mode": _state.mode.value})


@app.post("/api/v1/research/backtest")
def research_backtest(body: BacktestBody, principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    result = run_event_backtest(
        run_id=body.run_id or str(uuid.uuid4())[:8],
        as_of_date=body.as_of_date,
        bars=body.bars or [{"date": body.as_of_date, "symbol": "600000.SH", "close": 10.0}],
        signals=body.signals or [{"date": body.as_of_date, "symbol": "600000.SH", "side": "BUY", "price": 10.0}],
    )
    return envelope_ok(result.to_dict())


@app.post("/api/v1/research/candidate")
def research_candidate(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    proposal = construct_portfolio(
        run_id=str(uuid.uuid4())[:8],
        as_of_date="2026-06-16",
        ranked_symbols=[("600000.SH", 72.0), ("000001.SZ", 68.0)],
    )
    return envelope_ok(proposal.to_dict())


@app.get("/api/v1/research/reports")
def research_reports(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:read")
    report_dir = ROOT / "docs" / "ai" / "gateway"
    reports = sorted(p.name for p in report_dir.glob("*.json")) if report_dir.exists() else []
    return envelope_ok({"reports": reports})


@app.get("/api/v1/risk/status")
def risk_status(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "risk:read")
    return envelope_ok(_risk.snapshot().to_dict())


@app.post("/api/v1/risk/halt")
def risk_halt(body: HaltBody, principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    p = _require(principal, "risk:halt")
    _kill.halt(body.reason, p.user_id)
    _state.halt(p.user_id)
    _audit.emit("risk_halt", p.user_id, {"reason": body.reason})
    return envelope_ok({"halted": True, "mode": _state.mode.value})


@app.post("/api/v1/risk/reset-request")
def risk_reset_request(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    p = _require(principal, "risk:reset_request")
    st = _kill.request_reset(p.user_id)
    return envelope_ok(st.to_dict())


@app.get("/api/v1/paper/orders")
def paper_orders(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "paper:read")
    return envelope_ok({"orders": _paper.list_orders()})


@app.get("/api/v1/paper/fills")
def paper_fills(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "paper:read")
    return envelope_ok({"fills": _paper.list_fills()})


@app.get("/api/v1/paper/positions")
def paper_positions(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "paper:read")
    return envelope_ok({"positions": _paper.list_positions()})


@app.get("/api/v1/paper/pnl")
def paper_pnl(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "paper:read")
    return envelope_ok(_paper.pnl_summary())


@app.get("/api/v1/audit/events")
def audit_events(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "audit:read")
    return envelope_ok({"events": _audit.read_recent()})


@app.get("/api/v1/observability/traces/{trace_id}")
def get_trace(trace_id: str, principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "obs:read")
    return envelope_ok({"trace_id": trace_id, "spans": []})


@app.get("/api/v1/agents")
def list_agents(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "agents:invoke")
    return envelope_ok({"agents": _catalog.list_agents(), "governance": governance_report(_catalog.list_agents())})


@app.get("/api/v1/status")
def system_status(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    snap = _risk.snapshot()
    return envelope_ok({
        "mode": _state.mode.value,
        "autonomous_label": _state.max_autonomous_label(),
        "market_session": "CLOSED",
        "data_status": "WAREHOUSE_PRESENT",
        "capital": snap.capital_total_cny,
        "remaining_loss_budget": snap.remaining_loss_budget_cny,
        "kill_switch": snap.kill_switch,
        "blockers": snap.blockers,
        "paper_trading_only": PAPER_TRADING_ONLY,
    })


@app.get("/api/v1/sidecar/gc-mgc/status")
def sidecar_status(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:read")
    return envelope_ok(sidecar_research_status())


@app.post("/api/v1/sidecar/gc-mgc/features")
def sidecar_features(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    assert_not_bypassing_ashare_validation(caller="gc_mgc_sidecar", target_path="research/features")
    mbp = MBP10Snapshot(symbol="GC", ts="2026-06-16T10:00:00Z", bids=[(2400.0, 10)], asks=[(2400.5, 8)])
    return envelope_ok(compute_microstructure_features(mbp))


# QuantOS CN routes
from gateway.api.quantos import router as quantos_router
app.include_router(quantos_router)

# Portal static files
PORTAL_DIR = ROOT / "apps" / "portal-web"
if PORTAL_DIR.exists():
    app.mount("/portal/assets", StaticFiles(directory=PORTAL_DIR), name="portal-assets")

    @app.get("/portal")
    def portal_index() -> FileResponse:
        return FileResponse(PORTAL_DIR / "index.html")
