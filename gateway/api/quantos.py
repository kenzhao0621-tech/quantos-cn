"""QuantOS CN API routes — vn.py runtime + Qlib research."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from gateway.api.envelope import envelope_err, envelope_ok
from gateway.api.app import get_principal, _require
from gateway.auth.rbac import Principal
from integrations.vnpy.order_intent import OrderIntent
from services.vnpy_runtime.main import get_runtime

router = APIRouter(prefix="/api/v1/quantos", tags=["quantos"])


@router.get("/status")
def quantos_status(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from integrations.qlib.provider import CNMarketProvider
    from integrations.qlib.model_registry import load_registry
    rt = get_runtime()
    return envelope_ok({
        "product": "QuantOS CN",
        "vnpy_runtime": rt.status(),
        "qlib_provider": CNMarketProvider().health(),
        "model_registry": load_registry(),
        "real_execution_mode": "MANUAL_CONFIRM_ONLY",
    })


@router.get("/vnpy/doctor")
def vnpy_doctor(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    return envelope_ok(get_runtime().doctor())


@router.post("/vnpy/start")
def vnpy_start(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    return envelope_ok(get_runtime().start())


@router.post("/vnpy/stop")
def vnpy_stop(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    return envelope_ok(get_runtime().stop())


@router.get("/vnpy/gateways")
def list_gateways(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    rt = get_runtime()
    return envelope_ok({"gateways": rt.gateway_registry.list_gateways(), "active": rt.gateway_registry.active})


@router.get("/vnpy/events")
def recent_events(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "audit:read")
    return envelope_ok({"events": get_runtime().event_bridge.recent(50)})


@router.post("/paper/submit-intent")
def paper_submit(body: dict, principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    intent = OrderIntent.create(
        run_id=body.get("run_id", ""),
        symbol=body.get("symbol", ""),
        exchange=body.get("exchange", "SSE"),
        side=body.get("side", "BUY"),
        quantity=int(body.get("quantity", 100)),
        limit_price=float(body.get("limit_price", 0)),
        strategy_id=body.get("strategy_id", "default"),
        model_id=body.get("model_id", ""),
    )
    result = get_runtime().paper.submit(intent, data_fresh=body.get("data_fresh", True))
    return envelope_ok(result)


@router.post("/shadow/submit-intent")
def shadow_submit(body: dict, principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    intent = OrderIntent.create(
        run_id=body.get("run_id", ""),
        symbol=body.get("symbol", ""),
        exchange=body.get("exchange", "SSE"),
        side=body.get("side", "BUY"),
        quantity=int(body.get("quantity", 100)),
        limit_price=float(body.get("limit_price", 0)),
    )
    result = get_runtime().shadow.submit(intent, data_fresh=body.get("data_fresh", True))
    return envelope_ok(result)


@router.post("/reconcile")
def run_reconcile(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "paper:read")
    from integrations.vnpy.reconciliation import reconcile
    rt = get_runtime()
    report = reconcile(rt.paper.positions())
    return envelope_ok(report.to_dict())


@router.get("/qlib/doctor")
def qlib_doctor(principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from integrations.qlib.provider import CNMarketProvider
    return envelope_ok(CNMarketProvider().health())


@router.post("/qlib/baseline")
def qlib_baseline(body: dict, principal: Optional[Principal] = Depends(get_principal)) -> Dict[str, Any]:
    _require(principal, "research:run")
    from integrations.qlib.workflow import run_baseline_workflow
    result = run_baseline_workflow(as_of=body.get("as_of", "2026-06-16"), run_id=body.get("run_id", ""))
    return envelope_ok(result)
