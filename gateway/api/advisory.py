"""Advisory API — v2.2 cached, explainable single-stock advice + cache observability."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from gateway.api.envelope import envelope_err, envelope_ok
from gateway.auth.rbac import Principal, authenticate, require_permission
from gateway.config import GatewayConfig

router = APIRouter(prefix="/api/v1/advisory", tags=["advisory"])
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


@router.get("/analyze")
def advisory_analyze(
    symbol: str = Query(..., description="A股代码，如 600519.SH"),
    capital_cny: float = Query(10000.0, ge=100),
    position_weight: float = Query(0.30, gt=0, le=1.0),
    force_refresh: bool = Query(False, description="强制刷新：绕过缓存重算"),
    principal: Optional[Principal] = Depends(_principal),
) -> Dict[str, Any]:
    _require(principal, "market:read")
    from quant.application.advisory_service import get_advisory_service
    from quant.screener.symbol_search import normalize_symbol_input

    norm = normalize_symbol_input(symbol) or symbol.strip().upper()
    if not norm or "." not in norm:
        return envelope_err("INVALID_SYMBOL", "请输入有效的 A 股代码（如 600519 或 贵州茅台）")
    card = get_advisory_service().advise(
        norm, capital_cny=capital_cny, position_weight=position_weight,
        force_refresh=force_refresh,
    )
    if card.get("blocked"):
        return envelope_err("ADVISORY_BLOCKED", card.get("blocker_reason", "无法生成建议"),
                            details=card)
    return envelope_ok(card)


@router.get("/cache-status")
def advisory_cache_status(principal: Optional[Principal] = Depends(_principal)) -> Dict[str, Any]:
    _require(principal, "market:read")
    from quant.application.advisory_service import get_advisory_service

    return envelope_ok(get_advisory_service().cache_status())
