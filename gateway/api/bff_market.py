"""Backend-for-Frontend: market + jobs routes.

These routes are the ONLY market-data surface the portal consumes. They delegate
to the typed MarketDataService and the Job system. No private provider functions
(e.g. fetch_spot_snapshot) are imported here or in the portal.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from gateway.api.envelope import envelope_err, envelope_ok
from gateway.auth.rbac import Principal, authenticate, require_permission
from gateway.config import GatewayConfig
from gateway.jobs.manager import get_job_manager
from quant.application.live_market_service import fetch_live_snapshot, intraday_slots
from quant.application.market_data_service import get_market_data_service
from quant.domain.market_models import DataMode

router = APIRouter(tags=["bff-market"])
_cfg = GatewayConfig.load()
ROOT = Path(__file__).resolve().parents[2]
LIVE_STATE = ROOT / "data" / "gateway" / "live_snapshot.json"


async def _principal(
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


def _split_csv(value: str) -> list[str]:
    return [x.strip() for x in (value or "").replace("，", ",").split(",") if x.strip()]


class RefreshBody(BaseModel):
    datasets: list[str] = Field(default_factory=lambda: ["indices", "bars"])
    mode: str = "END_OF_DAY"


class JobBody(BaseModel):
    job_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Market BFF
# --------------------------------------------------------------------------
@router.get("/api/v1/market/overview")
def market_overview(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    svc = get_market_data_service()
    overview = svc.get_market_overview(mode=DataMode.END_OF_DAY)
    return envelope_ok(overview.to_dict(), provenance=overview.provenance)


@router.post("/api/v1/market/refresh")
def market_refresh(body: RefreshBody, principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    p = _require(principal, "research:run")
    try:
        mode = DataMode(body.mode)
    except ValueError:
        mode = DataMode.END_OF_DAY
    job = get_market_data_service().refresh_market_data(datasets=body.datasets, mode=mode)
    return envelope_ok(job.to_dict(), run_id=job.job_id)


@router.get("/api/v1/market/providers")
def market_providers(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    health = get_market_data_service().get_provider_health()
    return envelope_ok({"providers": [h.to_dict() for h in health]})


@router.get("/api/v1/market/coverage")
def market_coverage(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    cov = get_market_data_service().get_coverage()
    return envelope_ok({"coverage": [c.to_dict() for c in cov]})


@router.get("/api/v1/market/intraday-plan")
def market_intraday_plan(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    state = {}
    if LIVE_STATE.exists():
        state = json.loads(LIVE_STATE.read_text(encoding="utf-8"))
    return envelope_ok({
        "timezone": "Asia/Shanghai",
        "slots": intraday_slots(),
        "last_refresh": state.get("retrieved_at"),
        "last_success": state.get("success"),
        "last_provider": state.get("provider"),
    })


@router.get("/api/v1/market/intraday-schedule")
def market_intraday_schedule(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from quant.intraday_update_scheduler import intraday_schedule_status

    return envelope_ok(intraday_schedule_status())


@router.post("/api/v1/market/intraday-schedule")
def market_intraday_schedule_create(
    dry_run: bool = True,
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "research:run")
    from quant.intraday_update_scheduler import schedule_intraday_refresh

    return envelope_ok(schedule_intraday_refresh(dry_run=dry_run))


@router.get("/api/v1/market/live-snapshot")
def market_live_snapshot(
    require_live: bool = True,
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "market:read")
    return envelope_ok(fetch_live_snapshot(require_live=require_live))


@router.post("/api/v1/market/live-refresh")
def market_live_refresh(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    from quant.application.live_market_service import (
        ensure_live_quotes,
        live_quotes_ready,
        persist_live_snapshot,
        snapshot_rows,
    )

    snap = ensure_live_quotes(refresh=True)
    rows = snapshot_rows(snap)
    public = {k: v for k, v in snap.items() if k != "rows"}
    public["row_count"] = snap.get("row_count") or len(rows)
    public["quotes_ready"] = live_quotes_ready(snap)
    if not public["quotes_ready"]:
        return envelope_err(
            "LIVE_QUOTES_UNAVAILABLE",
            snap.get("reason") or "实时行情未就绪 — 行情源暂时不可用，请稍后重试",
            **{k: public[k] for k in ("row_count", "quotes_ready", "provider", "retrieved_at", "stale_fallback") if k in public},
            live_status=public,
        )
    persist_live_snapshot(snap)
    return envelope_ok(public)


@router.post("/api/v1/market/sync-all")
def market_sync_all(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    """One-click EOD index/bars refresh, warehouse sync, and live snapshot persist."""
    _require(principal, "research:run")
    from gateway.market_status import get_market_status_summary

    run_id = str(uuid.uuid4())[:8]
    py = ROOT / ".venv-china-quant" / "bin" / "python"
    targets = (
        ("indices", [str(py), "-m", "quant", "update-indices"]),
        ("bars", [str(py), "-m", "quant", "update-daily-bars"]),
        ("adj_factors", [str(py), "-m", "quant", "update-adj-factors"]),
        ("sectors", [str(py), "-m", "quant", "update-sectors"]),
        ("fundamentals", [str(py), "-m", "quant", "update-fundamentals"]),
        ("disclosures", [str(py), "-m", "quant", "update-disclosures"]),
    )

    def _run_target(target: str, cmd: list[str]) -> dict[str, Any]:
        try:
            r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=180)
            return {"target": target, "ok": r.returncode == 0, "tail": (r.stdout + r.stderr)[-500:]}
        except subprocess.TimeoutExpired:
            return {"target": target, "ok": False, "error": "timeout after 180s"}
        except Exception as exc:
            return {"target": target, "ok": False, "error": str(exc)[:120]}

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda tc: _run_target(*tc), targets))

    warehouse_sync: dict[str, Any] = {}
    try:
        from quant.warehouse import sync_from_partitions

        warehouse_sync = sync_from_partitions(run_id=run_id)
    except Exception as exc:
        warehouse_sync = {"error": str(exc)[:120]}

    snap = fetch_live_snapshot(require_live=False)
    if not snap.get("success") or (snap.get("row_count") or 0) < 100:
        snap = fetch_live_snapshot(require_live=True)
    from quant.application.live_market_service import normalize_snapshot_for_persist, persist_live_snapshot, snapshot_rows

    if snapshot_rows(snap):
        persist_live_snapshot(snap)
    else:
        LIVE_STATE.parent.mkdir(parents=True, exist_ok=True)
        LIVE_STATE.write_text(json.dumps(normalize_snapshot_for_persist(snap), ensure_ascii=False, indent=2), encoding="utf-8")

    market_status = get_market_status_summary()
    updates_ok = all(x.get("ok") for x in results)
    ok = updates_ok and not market_status.get("needs_index_sync") and market_status.get("live", {}).get("ok")

    return envelope_ok(
        {
            "run_id": run_id,
            "ok": ok,
            "updates": results,
            "warehouse_sync": warehouse_sync,
            "live_snapshot": {
                "success": snap.get("success"),
                "row_count": snap.get("row_count"),
                "provider": snap.get("provider"),
                "reason": snap.get("reason"),
            },
            "market_status": market_status,
            "message": market_status.get("labels", {}).get("pill", ""),
        },
        run_id=run_id,
    )


@router.get("/api/v1/screener/run")
def screener_run(
    preset: str = "balanced",
    top_n: int = 25,
    min_amount_cny: float = 5e7,
    as_of_date: Optional[str] = None,
    mode: str = "eod",
    preferred_sectors: str = "",
    excluded_sectors: str = "",
    price_min_cny: Optional[float] = None,
    price_max_cny: Optional[float] = None,
    capital_cny: Optional[float] = None,
    enforce_capital_price_ceiling: Optional[bool] = None,
    fast: bool = True,
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.preferences import load_preferences
    from quant.application.screener_service import get_screener_service

    if mode.lower() in ("live", "realtime", "intraday"):
        from quant.application.live_market_service import ensure_live_quotes, live_quotes_ready, snapshot_rows

        live_snap = ensure_live_quotes(refresh=False, max_age_sec=120)
        if not live_quotes_ready(live_snap):
            live_snap = ensure_live_quotes(refresh=True, max_age_sec=120)
        if not live_quotes_ready(live_snap):
            return envelope_err(
                "LIVE_QUOTES_UNAVAILABLE",
                live_snap.get("reason") or "实时行情未就绪 — 请稍后重试或检查行情源连接",
                live_status={k: v for k, v in live_snap.items() if k != "rows"},
                row_count=len(snapshot_rows(live_snap)),
            )

    prefs = load_preferences()
    pref_sectors = _split_csv(preferred_sectors) or prefs.preferred_sectors
    excl_sectors = _split_csv(excluded_sectors) or prefs.excluded_sectors
    top_n = max(5, min(int(top_n), 100))
    eff_cap = float(capital_cny) if capital_cny is not None else prefs.capital_cny
    eff_pmin = float(price_min_cny) if price_min_cny is not None else prefs.price_min_cny
    eff_pmax = float(price_max_cny) if price_max_cny is not None else prefs.price_max_cny
    eff_ceiling = (
        bool(enforce_capital_price_ceiling)
        if enforce_capital_price_ceiling is not None
        else prefs.enforce_capital_price_ceiling
    )
    use_fast = bool(fast)
    result = get_screener_service().screen(
        preset=preset or prefs.strategy_preset,
        top_n=top_n,
        min_amount_cny=float(min_amount_cny or prefs.min_amount_cny),
        as_of_date=as_of_date,
        mode=mode,
        preferred_sectors=pref_sectors,
        excluded_sectors=excl_sectors,
        price_min_cny=eff_pmin,
        price_max_cny=eff_pmax,
        capital_cny=eff_cap,
        enforce_capital_price_ceiling=eff_ceiling,
        fast=use_fast,
    )
    payload = result.to_dict()
    return envelope_ok(
        payload,
        provenance={
            "source": "canonical_duckdb",
            "engine": payload.get("screener_engine", "screener_v6_trading_agents_zh"),
            "agent_framework": "TradingAgents-CN",
            "fast_path": use_fast,
        },
    )


@router.get("/api/v1/screener/capabilities")
def screener_capabilities(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    return envelope_ok({
        "engine": "screener_v6_trading_agents_zh",
        "agent_framework": "TradingAgents-CN",
        "modes": ["eod", "live"],
        "fast_default": True,
        "features": [
            "multi_factor_ranking",
            "trading_agents_zh_overlay",
            "live_quote_integration",
            "portfolio_allocation",
            "diversity_constraints",
        ],
        "agent_roles": list(__import__("gateway.agents.cn_research.prompts", fromlist=["ROLE_PROMPTS"]).ROLE_PROMPTS.keys()),
    })


@router.get("/api/v1/screener/proof")
def screener_proof(
    preset: str = "balanced",
    top_n: int = 25,
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "market:read")
    from quant.application.screener_service import get_screener_service

    result = get_screener_service().prove_next_day(preset=preset, top_n=max(5, min(int(top_n), 100)))
    return envelope_ok(result, provenance={"source": "canonical_duckdb", "engine": "t_plus_1_proof"})


@router.get("/api/v1/screener/search")
def screener_search(
    q: str = "",
    limit: int = 10,
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "market:read")
    from quant.screener.symbol_search import search_symbols

    matches = search_symbols(q, limit=max(1, min(int(limit), 20)))
    return envelope_ok({"query": q, "matches": matches, "count": len(matches)})


@router.get("/api/v1/screener/analyze/{symbol}")
def screener_analyze(
    symbol: str,
    preset: str = "balanced",
    as_of_date: Optional[str] = None,
    mode: str = "eod",
    capital_cny: Optional[float] = None,
    preferred_sectors: str = "",
    excluded_sectors: str = "",
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.preferences import load_preferences
    from quant.application.screener_service import get_screener_service

    prefs = load_preferences()
    eff_cap = float(capital_cny) if capital_cny is not None else prefs.capital_cny
    if mode.lower() in ("live", "realtime", "intraday"):
        from quant.application.live_market_service import ensure_live_quotes

        ensure_live_quotes(refresh=True, max_age_sec=90)
    result = get_screener_service().analyze_symbol(
        symbol,
        preset=preset or prefs.strategy_preset,
        as_of_date=as_of_date,
        mode=mode,
        capital_cny=eff_cap,
        preferred_sectors=_split_csv(preferred_sectors) or prefs.preferred_sectors,
        excluded_sectors=_split_csv(excluded_sectors) or prefs.excluded_sectors,
    )
    if result.get("blocked"):
        return envelope_err(
            "SYMBOL_NOT_FOUND",
            result.get("blocker_reason", "无法分析该股票"),
            details=result,
        )
    return envelope_ok(result, provenance={"source": "canonical_duckdb", "engine": "symbol_analyze"})


@router.get("/api/v1/quant/regime")
def quant_regime(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from quant.regime import load_regime_from_warehouse

    return envelope_ok(load_regime_from_warehouse())


@router.get("/api/v1/quant/closed-loop")
def quant_closed_loop_status(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from pathlib import Path
    import json

    root = Path(__file__).resolve().parents[2]
    report_path = root / "artifacts" / "QUANTOS_CLOSED_LOOP_REPORT.json"
    if report_path.exists():
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        payload = {
            "production_ready": False,
            "status": "NOT_RUN",
            "hint": "Run: python scripts/run_quantos_closed_loop.py",
        }
    return envelope_ok(payload, provenance={"source": "quantos_closed_loop", "path": str(report_path.name)})


@router.get("/api/v1/quant/model-health")
def quant_model_health(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from pathlib import Path
    import json

    root = Path(__file__).resolve().parents[2]
    health_path = root / "artifacts" / "model_health_report.json"
    if health_path.exists():
        payload = json.loads(health_path.read_text(encoding="utf-8"))
    else:
        from quant.models.ml_scorer import get_ml_gate_status

        payload = {"status": "NOT_RUN", "ml_gate": get_ml_gate_status()}
    return envelope_ok(payload)


@router.get("/api/v1/screener/dossier/{symbol}")
def screener_dossier(
    symbol: str,
    preset: str = "balanced",
    as_of_date: Optional[str] = None,
    mode: str = "eod",
    preferred_sectors: str = "",
    excluded_sectors: str = "",
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.preferences import load_preferences
    from quant.application.screener_service import get_screener_service

    prefs = load_preferences()
    if mode.lower() in ("live", "realtime", "intraday"):
        from quant.application.live_market_service import ensure_live_quotes

        ensure_live_quotes(refresh=True, max_age_sec=90)
    return envelope_ok(
        get_screener_service().dossier(
            symbol=symbol,
            preset=preset or prefs.strategy_preset,
            as_of_date=as_of_date,
            mode=mode,
            preferred_sectors=_split_csv(preferred_sectors) or prefs.preferred_sectors,
            excluded_sectors=_split_csv(excluded_sectors) or prefs.excluded_sectors,
        ),
        provenance={"source": "canonical_duckdb", "engine": "candidate_dossier"},
    )


@router.post("/api/v1/screener/learn")
def screener_learn(
    preset: str = "balanced",
    top_n: int = 25,
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "research:run")
    from gateway.learning.screener_learning import run_screener_learning_cycle

    cycle = run_screener_learning_cycle(preset=preset, top_n=max(5, min(int(top_n), 100)))
    return envelope_ok(cycle, provenance={"source": "screener_learning", "engine": "t_plus_1_agent_feedback"})


@router.get("/api/v1/screener/learn/latest")
def screener_learn_latest(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.learning.screener_learning import latest_learning_report

    report = latest_learning_report()
    if not report:
        return envelope_ok({"status": "NOT_RUN", "hint": "运行「策略自验证学习」生成首份报告"})
    return envelope_ok(report)


@router.post("/api/v1/screener/report/{symbol}")
def screener_report_pdf(
    symbol: str,
    preset: str = "balanced",
    mode: str = "eod",
    preferred_sectors: str = "",
    excluded_sectors: str = "",
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "research:read")
    from gateway.preferences import load_preferences
    from quant.application.screener_service import get_screener_service
    from quant.screener.screener_report_pdf import render_screener_analysis_pdf

    prefs = load_preferences()
    if mode.lower() in ("live", "realtime", "intraday"):
        from quant.application.live_market_service import ensure_live_quotes

        ensure_live_quotes(refresh=True, max_age_sec=90)
    dossier = get_screener_service().dossier(
        symbol=symbol,
        preset=preset or prefs.strategy_preset,
        mode=mode,
        preferred_sectors=_split_csv(preferred_sectors) or prefs.preferred_sectors,
        excluded_sectors=_split_csv(excluded_sectors) or prefs.excluded_sectors,
    )
    if dossier.get("blocked"):
        return envelope_err("SYMBOL_NOT_FOUND", dossier.get("blocker_reason", "无法生成报告"), details=dossier)
    paths = render_screener_analysis_pdf(dossier, symbol=symbol)
    if not paths.get("pdf_ready"):
        return envelope_err("PDF_RENDER_FAILED", "PDF 渲染失败，请检查 Playwright/ReportLab 依赖", details=paths)
    return envelope_ok(paths)


@router.get("/api/v1/screener/report/download")
def screener_report_download(
    file: str,
    principal: Optional[Principal] = Depends(_principal),
):
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from pathlib import Path

    _require(principal, "research:read")
    root = Path(__file__).resolve().parents[2]
    report_dir = root / "docs" / "ai" / "daily-trading" / "screener_reports"
    safe = Path(file).name
    path = report_dir / safe
    if not path.exists() or not safe.endswith(".pdf"):
        raise HTTPException(status_code=404, detail="report not found")
    return FileResponse(path, media_type="application/pdf", filename=safe)


# --------------------------------------------------------------------------
# Job system
# --------------------------------------------------------------------------
@router.post("/api/v1/jobs")
def create_job(body: JobBody, principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    p = _require(principal, "research:run")
    job = get_job_manager().submit(job_type=body.job_type, payload=body.payload)
    return envelope_ok(job.to_dict(), run_id=job.job_id)


@router.get("/api/v1/jobs")
def list_jobs(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    jobs = get_job_manager().list_jobs()
    return envelope_ok({"jobs": [j.to_dict() for j in jobs]})


@router.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str, principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    job = get_job_manager().get(job_id)
    if not job:
        return envelope_err("NOT_FOUND", f"job {job_id} not found")
    return envelope_ok(job.to_dict(), run_id=job.job_id)


@router.get("/api/v1/jobs/{job_id}/events")
def job_events(job_id: str, principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    job = get_job_manager().get(job_id)
    if not job:
        return envelope_err("NOT_FOUND", f"job {job_id} not found")
    return envelope_ok({
        "job_id": job.job_id,
        "status": job.status,
        "percent": job.percent,
        "current_step": job.current_step,
        "events": [e.__dict__ if hasattr(e, "__dict__") else e for e in job.events],
    })


@router.post("/api/v1/jobs/{job_id}/cancel")
def cancel_job(job_id: str, principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    ok = get_job_manager().cancel(job_id)
    return envelope_ok({"job_id": job_id, "cancelled": ok})


@router.post("/api/v1/jobs/{job_id}/retry")
def retry_job(job_id: str, principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    p = _require(principal, "research:run")
    job = get_job_manager().retry(job_id)
    if not job:
        return envelope_err("NOT_FOUND", f"job {job_id} not found")
    return envelope_ok(job.to_dict(), run_id=job.job_id)
