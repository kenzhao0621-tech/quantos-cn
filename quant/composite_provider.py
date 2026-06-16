"""Composite market data provider with config-driven routing and DQ gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

from quant._config import _DEFAULT_ROUTING, load_config
from quant.data_quality import run_snapshot_quality_checks
from quant.provider_result import ProviderResult, ProviderStatus
from quant.providers.akshare_family import (
    AkshareEastmoneyProvider,
    AkshareSinaProvider,
    AkshareSplitMarketProvider,
)
from quant.providers.jqdata_provider import JQDataProvider
from quant.providers.manual_snapshot import ManualSnapshotProvider
from quant.providers.supermind_provider import SupermindProvider
from quant.providers.tushare_provider import TushareProvider


class MarketDataProvider(Protocol):
    name: str

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult: ...


@dataclass
class CompositeFetchResult:
    dataset: str
    result: Optional[ProviderResult]
    attempts: list[ProviderResult] = field(default_factory=list)
    selection_reason: str = ""

    @property
    def ok(self) -> bool:
        return self.result is not None and self.result.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "success": self.ok,
            "winner": self.result.to_dict() if self.result else None,
            "attempts": [a.to_dict() for a in self.attempts],
            "selection_reason": self.selection_reason,
        }


def _build_registry() -> dict[str, MarketDataProvider]:
    return {
        "akshare_eastmoney": AkshareEastmoneyProvider(),
        "akshare_split": AkshareSplitMarketProvider(),
        "akshare_sina": AkshareSinaProvider(),
        "tushare": TushareProvider(),
        "jqdata": JQDataProvider(),
        "supermind": SupermindProvider(),
        "manual_snapshot": ManualSnapshotProvider(),
    }


def _copy_result(result: ProviderResult, *, attempt: int = 0, **overrides: Any) -> ProviderResult:
    fields = {
        "provider": result.provider,
        "dataset": result.dataset,
        "status": result.status,
        "payload": result.payload,
        "error": result.error,
        "attempt": attempt or result.attempt,
        "elapsed_ms": result.elapsed_ms,
        "retrieved_at": result.retrieved_at,
        "data_hash": result.data_hash,
        "row_count": result.row_count,
        "freshness": result.freshness,
        "limitations": result.limitations,
        "endpoint": result.endpoint,
        "source_dataset": result.source_dataset,
        "run_id": result.run_id,
        "market_date": result.market_date,
        "is_live": result.is_live,
        "is_end_of_day": result.is_end_of_day,
        "is_manual": result.is_manual,
        "is_fixture": result.is_fixture,
    }
    fields.update(overrides)
    return ProviderResult(**fields)


class CompositeMarketDataProvider:
    """Try providers in routing order; DQ gate before winner selection."""

    def __init__(
        self,
        *,
        routing_path: Optional[Path] = None,
        registry: Optional[dict[str, MarketDataProvider]] = None,
    ) -> None:
        self.routing_path = routing_path
        self.registry = registry or _build_registry()
        self._routing = load_config("routing", defaults=_DEFAULT_ROUTING)

    def reload_routing(self) -> None:
        self._routing = load_config("routing", defaults=_DEFAULT_ROUTING)

    def provider_chain(
        self,
        dataset: str,
        *,
        route_mode: str | None = None,
        provider_filter: str | None = None,
        live_only: bool = False,
    ) -> list[str]:
        modes = self._routing.get("modes", {})
        if live_only and dataset == "spot_quotes":
            chain = list(modes.get("spot_quotes_live", {}).get("providers", []))
        elif route_mode == "latest_available" and dataset == "spot_quotes":
            chain = list(modes.get("spot_quotes_latest_available", {}).get("providers", []))
        else:
            entry = self._routing.get("datasets", {}).get(dataset, {})
            chain = list(entry.get("providers", []))
        if not chain:
            entry = self._routing.get("datasets", {}).get(dataset, {})
            chain = list(entry.get("providers", []))
        if live_only:
            chain = [p for p in chain if p not in ("manual_snapshot", "fixture")]
        if provider_filter:
            chain = [p for p in chain if p == provider_filter]
        return chain

    def fetch(self, dataset: str, **kwargs: Any) -> CompositeFetchResult:
        route_mode = kwargs.get("route_mode")
        provider_filter = kwargs.get("provider_filter")
        live_only = bool(kwargs.get("live_only"))
        min_rows = kwargs.get("min_rows", 5000 if dataset == "spot_quotes" else 1)

        chain = self.provider_chain(
            dataset,
            route_mode=route_mode,
            provider_filter=provider_filter,
            live_only=live_only,
        )
        attempts: list[ProviderResult] = []
        winner: Optional[ProviderResult] = None
        selection_reason = "no provider succeeded"

        for idx, name in enumerate(chain, start=1):
            provider = self.registry.get(name)
            if provider is None:
                attempts.append(
                    ProviderResult(
                        provider=name,
                        dataset=dataset,
                        status=ProviderStatus.SKIPPED,
                        error="unknown provider in routing",
                        attempt=idx,
                    )
                )
                continue
            result = provider.fetch(dataset, **kwargs)
            if result.attempt == 0:
                result = _copy_result(result, attempt=idx)
            attempts.append(result)

            if not result.ok or winner is not None:
                continue

            meta = {
                "is_fixture": result.is_fixture,
                "is_manual": result.is_manual or name == "manual_snapshot",
                "require_non_fixture": live_only,
                "freshness": result.freshness,
            }
            qr = run_snapshot_quality_checks(
                dataset,
                result.payload,
                data_hash=result.data_hash,
                min_rows=min_rows,
                provider=result.provider,
                source_dataset=result.source_dataset,
                doc_meta=meta,
            )
            if not qr.passed:
                attempts[-1] = _copy_result(
                    result,
                    status=ProviderStatus.FAILED,
                    error=f"DQ gate: {'; '.join(qr.errors + qr.missing_fields)}",
                )
                continue

            if live_only and (result.is_manual or result.is_fixture or not result.is_live):
                attempts[-1] = _copy_result(
                    result,
                    status=ProviderStatus.FAILED,
                    error="live_only: rejected non-live provider result",
                )
                continue

            winner = result
            selection_reason = f"first passing provider after DQ gate (attempt {idx}: {name})"

        return CompositeFetchResult(
            dataset=dataset,
            result=winner,
            attempts=attempts,
            selection_reason=selection_reason,
        )

    def fetch_market_snapshot(self, **kwargs: Any) -> dict[str, CompositeFetchResult]:
        datasets = kwargs.get("datasets") or [
            "indices",
            "spot_quotes",
            "trading_calendar",
            "sector_boards",
        ]
        return {ds: self.fetch(ds, **kwargs) for ds in datasets}
