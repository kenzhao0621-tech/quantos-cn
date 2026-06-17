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
    snap = fetch_live_snapshot(require_live=True)
    if not snap.get("success") or (snap.get("row_count") or 0) < 100:
        snap = fetch_live_snapshot(require_live=False)
    LIVE_STATE.parent.mkdir(parents=True, exist_ok=True)
    LIVE_STATE.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    return envelope_ok(snap)


@router.post("/api/v1/market/sync-all")
def market_sync_all(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    """One-click EOD index/bars refresh, warehouse sync, and live snapshot persist."""
    _require(principal, "research:run")
    from gateway.market_status import get_market_status_summary

    run_id = str(uuid.uuid4())[:8]
    py = ROOT / ".venv-china-quant" / "bin" / "python"
    results: list[dict[str, Any]] = []
    for target, cmd in (
        ("indices", [str(py), "-m", "quant", "update-indices"]),
        ("bars", [str(py), "-m", "quant", "update-daily-bars"]),
    ):
        try:
            r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=300)
            results.append({
                "target": target,
                "ok": r.returncode == 0,
                "tail": (r.stdout + r.stderr)[-500:],
            })
        except subprocess.TimeoutExpired:
            results.append({"target": target, "ok": False, "error": "timeout after 300s"})
        except Exception as exc:
            results.append({"target": target, "ok": False, "error": str(exc)[:120]})

    warehouse_sync: dict[str, Any] = {}
    try:
        from quant.warehouse import sync_from_partitions

        warehouse_sync = sync_from_partitions(run_id=run_id)
    except Exception as exc:
        warehouse_sync = {"error": str(exc)[:120]}

    snap = fetch_live_snapshot(require_live=False)
    if not snap.get("success") or (snap.get("row_count") or 0) < 100:
        snap = fetch_live_snapshot(require_live=True)
    LIVE_STATE.parent.mkdir(parents=True, exist_ok=True)
    LIVE_STATE.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

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
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "market:read")
    from gateway.preferences import load_preferences
    from quant.application.screener_service import get_screener_service

    prefs = load_preferences()
    pref_sectors = _split_csv(preferred_sectors) or prefs.preferred_sectors
    excl_sectors = _split_csv(excluded_sectors) or prefs.excluded_sectors
    top_n = max(5, min(int(top_n), 100))
    result = get_screener_service().screen(
        preset=preset or prefs.strategy_preset,
        top_n=top_n,
        min_amount_cny=float(min_amount_cny or prefs.min_amount_cny),
        as_of_date=as_of_date,
        mode=mode,
        preferred_sectors=pref_sectors,
        excluded_sectors=excl_sectors,
    )
    return envelope_ok(result.to_dict(), provenance={"source": "canonical_duckdb", "engine": "multi_factor_screener"})


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
