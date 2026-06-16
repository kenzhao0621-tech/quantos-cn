"""Composite market data provider with config-driven routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

from quant._config import CONFIG_DIR, _DEFAULT_ROUTING, load_config
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

    @property
    def ok(self) -> bool:
        return self.result is not None and self.result.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "success": self.ok,
            "winner": self.result.to_dict() if self.result else None,
            "attempts": [a.to_dict() for a in self.attempts],
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


class CompositeMarketDataProvider:
    """Try providers in routing order; record every attempt."""

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

    def provider_chain(self, dataset: str) -> list[str]:
        datasets = self._routing.get("datasets", {})
        entry = datasets.get(dataset, {})
        return list(entry.get("providers", []))

    def fetch(self, dataset: str, **kwargs: Any) -> CompositeFetchResult:
        chain = self.provider_chain(dataset)
        attempts: list[ProviderResult] = []
        winner: Optional[ProviderResult] = None

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
            # Re-tag attempt order if provider did not set it
            if result.attempt == 0:
                result = ProviderResult(
                    provider=result.provider,
                    dataset=result.dataset,
                    status=result.status,
                    payload=result.payload,
                    error=result.error,
                    attempt=idx,
                    elapsed_ms=result.elapsed_ms,
                    retrieved_at=result.retrieved_at,
                    data_hash=result.data_hash,
                    row_count=result.row_count,
                    freshness=result.freshness,
                    limitations=result.limitations,
                )
            attempts.append(result)
            if result.ok and winner is None:
                winner = result

        return CompositeFetchResult(dataset=dataset, result=winner, attempts=attempts)

    def fetch_market_snapshot(self, **kwargs: Any) -> dict[str, CompositeFetchResult]:
        """Fetch core datasets for a daily market snapshot."""
        datasets = kwargs.get("datasets") or [
            "indices",
            "spot_quotes",
            "trading_calendar",
            "sector_boards",
        ]
        return {ds: self.fetch(ds, **kwargs) for ds in datasets}
