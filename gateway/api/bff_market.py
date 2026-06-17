"""Backend-for-Frontend: market + jobs routes.

These routes are the ONLY market-data surface the portal consumes. They delegate
to the typed MarketDataService and the Job system. No private provider functions
(e.g. fetch_spot_snapshot) are imported here or in the portal.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from gateway.api.envelope import envelope_err, envelope_ok
from gateway.auth.rbac import Principal, authenticate, require_permission
from gateway.config import GatewayConfig
from gateway.jobs.manager import get_job_manager
from quant.application.market_data_service import get_market_data_service
from quant.domain.market_models import DataMode

router = APIRouter(tags=["bff-market"])
_cfg = GatewayConfig.load()


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


@router.get("/api/v1/screener/run")
def screener_run(
    preset: str = "balanced",
    top_n: int = 25,
    min_amount_cny: float = 5e7,
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "market:read")
    from quant.application.screener_service import get_screener_service

    top_n = max(5, min(int(top_n), 100))
    result = get_screener_service().screen(
        preset=preset, top_n=top_n, min_amount_cny=float(min_amount_cny)
    )
    return envelope_ok(result.to_dict(), provenance={"source": "canonical_duckdb", "engine": "multi_factor_screener"})


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
