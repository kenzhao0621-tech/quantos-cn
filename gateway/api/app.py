"""Gateway FastAPI application."""

from quant.paths import desktop_reports_root

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from gateway import __version__, PAPER_TRADING_ONLY, REAL_MONEY_EXECUTION_DISABLED
from gateway.env_loader import load_project_env

load_project_env()
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
_runtime = load_runtime_state()
try:
    _initial_mode = TradingMode(_runtime.get("mode", _cfg.mode))
except ValueError:
    _initial_mode = TradingMode.RESEARCH_ONLY
_state = StateMachine(_initial_mode)
_risk.set_mode(_initial_mode.value)
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


class PaperOrderBody(BaseModel):
    symbol: str
    side: str = "BUY"
    quantity: int = 100
    limit_price: float = 0.0


class BacktestBody(BaseModel):
    as_of_date: str = ""
    run_id: str = ""
    bars: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    preset: str = "balanced"
    lookback_days: int = 60
    top_n: int = 5
    engine: str = "screener_portfolio"


@app.get("/")
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/portal", status_code=302)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/build-info")
def build_info() -> Dict[str, Any]:
    from gateway.build_info import version_payload
    return version_payload()


@app.get("/ready")
def ready() -> Dict[str, Any]:
    from gateway.lifecycle import readiness_payload
    return readiness_payload(mode=_state.mode.value)


@app.get("/api/v1/market/status")
def market_status(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.market_status import get_market_status_summary

    runtime = load_runtime_state()
    freshness = get_market_status_summary()
    return envelope_ok({
        "mode": _state.mode.value,
        "session": "CLOSED",
        "paper_trading_only": PAPER_TRADING_ONLY,
        "runtime": runtime,
        **freshness,
    }, request_id=str(uuid.uuid4()))


@app.get("/api/v1/market/snapshot")
def market_snapshot(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from quant.application.market_data_service import get_market_data_service
    from quant.domain.market_models import DataMode

    overview = get_market_data_service().get_market_overview(mode=DataMode.END_OF_DAY)
    return envelope_ok(overview.to_dict(), provenance=overview.provenance)


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
    from gateway.api.operations import run_daily_report_async
    run_id = run_daily_report_async(p.user_id)
    _audit.emit("daily_run", p.user_id, {"run_id": run_id})
    return envelope_ok(
        {
            "run_id": run_id,
            "status": "RUNNING",
            "mode": _state.mode.value,
            "message": "????????????????? China_A_Share_Daily_Reports ???",
            "desktop_root": str(desktop_reports_root()),
        },
        run_id=run_id,
    )


@app.post("/api/v1/research/backtest")
def research_backtest(body: BacktestBody, principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    if body.engine == "screener_portfolio" or (not body.bars and not body.signals):
        from gateway.backtest.screener_backtest import run_screener_portfolio_backtest

        result = run_screener_portfolio_backtest(
            preset=body.preset,
            lookback_days=body.lookback_days,
            top_n=body.top_n,
        )
        return envelope_ok(result)
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
    from quant.application.screener_service import get_screener_service

    screen = get_screener_service().screen(preset="balanced", top_n=10)
    if screen.blocked:
        return envelope_err("SCREENER_BLOCKED", screen.blocker_reason)
    ranked = [
        (c.symbol, max(0.0, min(100.0, 50.0 + c.score * 8.0)))
        for c in screen.candidates
    ]
    proposal = construct_portfolio(
        run_id=str(uuid.uuid4())[:8],
        as_of_date=screen.as_of_date or "",
        ranked_symbols=ranked,
    )
    return envelope_ok(proposal.to_dict())


@app.get("/api/v1/research/reports")
def research_reports(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:read")
    report_dir = ROOT / "docs" / "ai" / "gateway"
    reports = sorted(p.name for p in report_dir.glob("*.json")) if report_dir.exists() else []
    daily = ROOT / "docs" / "ai" / "daily-trading" / "daily"
    daily_pdfs = sorted(p.name for p in daily.glob("*_DAILY_QUANT_REPORT.pdf")) if daily.exists() else []
    return envelope_ok({"reports": reports, "daily_pdfs": daily_pdfs})


@app.get("/api/v1/research/reports/download")
def research_report_download(
    file: str,
    principal: Optional[Principal] = Depends(get_principal),
):
    _require(principal, "research:read")
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    daily = ROOT / "docs" / "ai" / "daily-trading" / "daily"
    safe = Path(file).name
    path = daily / safe
    if not path.exists() or not safe.endswith(".pdf"):
        raise HTTPException(status_code=404, detail="report not found")
    return FileResponse(path, media_type="application/pdf", filename=safe)


@app.get("/api/v1/gateway/capabilities")
def gateway_capabilities(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway import __version__
    from gateway.monitoring.intraday_background import intraday_refresh_status
    from gateway.learning.screener_learning import latest_learning_report

    return envelope_ok({
        "gateway_version": __version__,
        "product": "QuantOS Gateway",
        "alignment": "gateway-portal-requirements v2.1",
        "capabilities": {
            "unified_api": True,
            "envelope_contract": True,
            "rbac": True,
            "audit_events": True,
            "observability_traces": True,
            "agent_framework": "TradingAgents-CN",
            "screener_engine": "screener_v6_trading_agents_zh",
            "live_quotes_intraday_refresh": intraday_refresh_status(),
            "screener_learning": latest_learning_report() is not None,
            "pdf_exports": ["daily_quant_report", "screener_symbol_analysis", "paper_close_report"],
            "paper_autopilot": True,
            "risk_engine": True,
            "data_fabric": True,
        },
        "endpoints": {
            "screener_run": "/api/v1/screener/run",
            "screener_learn": "/api/v1/screener/learn",
            "screener_report_pdf": "/api/v1/screener/report/{symbol}",
            "daily_report_pdf": "/api/v1/research/reports/download",
            "live_refresh": "/api/v1/market/live-refresh",
            "gateway_capabilities": "/api/v1/gateway/capabilities",
        },
    })


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


@app.get("/api/v1/paper/account")
def paper_account(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "paper:read")
    return envelope_ok(_paper.account_summary())


@app.post("/api/v1/paper/mark-to-market")
def paper_mark_to_market(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "paper:trade")
    from quant.application.live_market_service import ensure_live_quotes, live_price_map

    ensure_live_quotes(refresh=True, max_age_sec=120)
    result = _paper.mark_to_market(prefer_live=True)
    result["live_prices"] = len(live_price_map())
    return envelope_ok({**result, "account": _paper.account_summary()})


@app.post("/api/v1/paper/order")
def paper_submit_order(
    body: PaperOrderBody,
    principal: Optional[Principal] = Depends(get_principal),
) -> Dict[str, Any]:
    p = _require(principal, "paper:trade")
    if _state.mode != TradingMode.PAPER_TRADING:
        return envelope_err("PAPER_NOT_STARTED", "请先点击「启动 Paper」再模拟下单")
    sym = body.symbol.strip().upper()
    if not sym.endswith((".SH", ".SZ", ".BJ")):
        code = "".join(c for c in sym if c.isdigit())
        if code.startswith("6"):
            sym = f"{code.zfill(6)}.SH"
        elif code.startswith(("4", "8")):
            sym = f"{code.zfill(6)}.BJ"
        else:
            sym = f"{code.zfill(6)}.SZ"
    qty = int(body.quantity)
    if body.side.upper() == "BUY" and (qty < 100 or qty % 100 != 0):
        return envelope_err("INVALID_LOT", "买入数量须为 100 的整数倍")
    limit_px = float(body.limit_price or 0)
    if limit_px <= 0:
        from quant.application.live_market_service import live_price_map

        limit_px = live_price_map().get(sym, 0.0)
    if limit_px <= 0:
        return envelope_err("NO_PRICE", "无法获取参考价 — 请先刷新实时行情或填写限价")
    intent = OrderIntent(
        client_order_id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4())[:8],
        strategy_id="manual_desk",
        model_id="paper_desk",
        symbol=sym,
        side=body.side.upper(),
        quantity=qty,
        limit_price=limit_px,
        notional_cny=limit_px * qty,
    )
    order = _paper.submit(intent, data_fresh=True, market_price=limit_px)
    _audit.emit("paper_manual_order", p.user_id, {
        "symbol": sym,
        "side": body.side.upper(),
        "state": order.state.value,
        "reject_reason": order.reject_reason,
    })
    if order.state.value == "REJECTED":
        return envelope_err("ORDER_REJECTED", order.reject_reason or "订单被拒绝", order=order.to_dict())
    return envelope_ok({"order": order.to_dict(), "account": _paper.account_summary()})


@app.get("/api/v1/paper/monitor")
def paper_monitor_status(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "paper:read")
    from gateway.paper.autopilot_monitor import monitor_status

    return envelope_ok(monitor_status(_paper))


@app.post("/api/v1/paper/monitor/tick")
def paper_monitor_tick(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    p = _require(principal, "paper:trade")
    if _state.mode != TradingMode.PAPER_TRADING:
        return envelope_err("PAPER_NOT_STARTED", "请先启动 Paper")
    from gateway.paper.autopilot_monitor import run_monitor_tick

    result = run_monitor_tick(_paper, user_id=p.user_id, refresh_quotes=True)
    if not result.get("ok"):
        return envelope_err("MONITOR_BLOCKED", result.get("reason", "监控被阻断"), **result)
    return envelope_ok(result)


@app.post("/api/v1/paper/monitor/stop")
def paper_monitor_stop(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "paper:trade")
    from gateway.paper.autopilot_monitor import load_monitor_state, save_monitor_state

    st = load_monitor_state()
    st["enabled"] = False
    save_monitor_state(st)
    return envelope_ok(st)


@app.get("/api/v1/paper/reports")
def paper_reports_list(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "paper:read")
    from gateway.config import ROOT

    daily = ROOT / "docs" / "ai" / "daily-trading" / "daily"
    reports = []
    if daily.exists():
        for pdf in sorted(daily.glob("*_PAPER_OPS.pdf"), reverse=True)[:30]:
            d = pdf.name.split("_")[0]
            reports.append({
                "trade_date": d,
                "path_pdf": str(pdf),
                "download_url": f"/api/v1/paper/reports/download?file={pdf.name}",
                "label": pdf.stem.replace("_", " "),
            })
    return envelope_ok({"reports": reports})


@app.get("/api/v1/paper/reports/download")
def paper_report_download(
    file: str,
    principal: Optional[Principal] = Depends(get_principal),
):
    _require(principal, "paper:read")
    from gateway.config import ROOT

    daily = ROOT / "docs" / "ai" / "daily-trading" / "daily"
    safe = Path(file).name
    path = daily / safe
    if not path.exists() or not safe.endswith(".pdf"):
        raise HTTPException(status_code=404, detail="report not found")
    return FileResponse(path, media_type="application/pdf", filename=safe)


@app.post("/api/v1/paper/reports/generate-close")
def paper_report_generate_close(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    p = _require(principal, "paper:trade")
    from datetime import datetime

    from quant.trading_ops_report import generate_trading_ops_reports

    trade_date = datetime.now().strftime("%Y-%m-%d")
    paths = generate_trading_ops_reports(trade_date, session="close")
    paper_pdf = (paths.get("modes") or {}).get("paper", {}).get("pdf", "")
    _audit.emit("paper_close_report", p.user_id, {"trade_date": trade_date, "pdf": paper_pdf})
    return envelope_ok({
        "trade_date": trade_date,
        "paths": paths,
        "download_url": f"/api/v1/paper/reports/download?file={Path(paper_pdf).name}" if paper_pdf else "",
    })


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

# V4 operational routes
from gateway.api import operations as ops_module
ops_module.configure(state=_state, kill=_kill, risk=_risk, paper=_paper, shadow=_shadow, audit=_audit)
app.include_router(ops_module.router)

# V6 Backend-for-Frontend market + jobs routes (typed MarketDataService boundary)
from gateway.api.bff_market import router as bff_market_router
app.include_router(bff_market_router)

# Portal static files
PORTAL_DIR = ROOT / "apps" / "portal-web"
if PORTAL_DIR.exists():
    from gateway.build_info import portal_build_id

    _PORTAL_BUILD = portal_build_id()

    class _PortalStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope):  # type: ignore[override]
            response = await super().get_response(path, scope)
            if path.endswith((".js", ".css")):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return response

    app.mount("/portal/assets", _PortalStaticFiles(directory=PORTAL_DIR), name="portal-assets")

    @app.get("/portal")
    def portal_index() -> HTMLResponse:
        html = (PORTAL_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace("__BUILD_ID__", _PORTAL_BUILD)
        return HTMLResponse(
            content=html,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "X-Portal-Build": _PORTAL_BUILD,
            },
        )


@app.on_event("startup")
def _startup_intraday_refresh() -> None:
    from gateway.monitoring.intraday_background import start_background_intraday_refresh

    start_background_intraday_refresh()
