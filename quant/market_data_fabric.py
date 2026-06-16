"""Provider-neutral market data fabric with freshness and cross-source gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from quant._config import CONFIG_DIR, load_config
from quant.composite_provider import CompositeFetchResult, _copy_result
from quant.cross_source_reconcile import reconcile_live_sources
from quant.data_quality import run_snapshot_quality_checks
from quant.freshness_contract import FreshnessValidationResult
from quant.provider_result import ProviderResult, ProviderStatus
from quant.providers.akshare_family import (
    AkshareEastmoneyProvider,
    AkshareSinaProvider,
    AkshareSplitMarketProvider,
)
from quant.providers.authorized_web_provider import AuthorizedWebDatasetProvider
from quant.providers.baostock_provider import BaoStockProvider
from quant.providers.jqdata_provider import JQDataProvider
from quant.providers.manual_snapshot import ManualSnapshotProvider
from quant.providers.official_file_provider import OfficialFileDownloadProvider
from quant.providers.qmt_provider import QMTMarketDataProvider
from quant.providers.rqdata_provider import RQDataProvider
from quant.providers.supermind_provider import SupermindProvider
from quant.providers.tushare_provider import TushareProvider

_DEFAULT_ROUTING_V2: dict[str, Any] = {
    "version": "2",
    "routing": {
        "spot_quotes": ["akshare_sina", "tushare", "baostock", "manual_snapshot"],
        "live_spot": ["rqdata", "qmt_market_data", "akshare_sina"],
        "indices": ["tushare", "akshare_sina"],
        "index_daily": ["tushare", "baostock"],
        "daily_bars": ["tushare", "baostock"],
        "trading_calendar": ["tushare", "akshare_sina", "baostock"],
        "security_master": ["tushare", "jqdata"],
    },
}


def _build_registry_v2() -> dict[str, Any]:
    return {
        "akshare_eastmoney": AkshareEastmoneyProvider(),
        "akshare_split": AkshareSplitMarketProvider(),
        "akshare_sina": AkshareSinaProvider(),
        "tushare": TushareProvider(),
        "jqdata": JQDataProvider(),
        "rqdata": RQDataProvider(),
        "baostock": BaoStockProvider(),
        "qmt_market_data": QMTMarketDataProvider(),
        "authorized_web": AuthorizedWebDatasetProvider(),
        "official_file": OfficialFileDownloadProvider(),
        "supermind": SupermindProvider(),
        "manual_snapshot": ManualSnapshotProvider(),
    }


@dataclass
class FabricFetchResult:
    dataset: str
    result: Optional[ProviderResult]
    attempts: list[ProviderResult] = field(default_factory=list)
    selection_reason: str = ""
    freshness: Optional[FreshnessValidationResult] = None
    cross_source: Optional[dict[str, Any]] = None
    quarantined: bool = False

    @property
    def ok(self) -> bool:
        return self.result is not None and self.result.ok and not self.quarantined

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "success": self.ok,
            "winner": self.result.to_dict() if self.result else None,
            "attempts": [a.to_dict() for a in self.attempts],
            "selection_reason": self.selection_reason,
            "freshness": self.freshness.to_dict() if self.freshness else None,
            "cross_source": self.cross_source,
            "quarantined": self.quarantined,
        }


class MarketDataFabric:
    """Dataset-specific routing with capability, freshness, DQ, and cross-source gates."""

    def __init__(self, *, registry: Optional[dict[str, Any]] = None) -> None:
        self.registry = registry or _build_registry_v2()
        self._routing = load_config("routing_v2", defaults=_DEFAULT_ROUTING_V2)

    def reload_routing(self) -> None:
        self._routing = load_config("routing_v2", defaults=_DEFAULT_ROUTING_V2)

    def provider_chain(
        self,
        dataset: str,
        *,
        mode: str = "latest_completed",
        live_only: bool = False,
        provider_filter: str | None = None,
    ) -> list[str]:
        routes = self._routing.get("routing", {})
        key = "live_spot" if live_only and dataset == "spot_quotes" else dataset
        chain = list(routes.get(key, routes.get(dataset, [])))
        if live_only:
            chain = [p for p in chain if p not in ("manual_snapshot", "tushare", "baostock")]
        if provider_filter:
            chain = [p for p in chain if p == provider_filter]
        return chain

    def _freshness_check(
        self, provider: Any, dataset: str, result: ProviderResult, **kwargs: Any,
    ) -> FreshnessValidationResult:
        if hasattr(provider, "freshness_validate"):
            return provider.freshness_validate(dataset, result, **kwargs)
        from quant.providers.adapter_mixin import default_freshness_validate
        sla = "live_spot" if kwargs.get("require_live") else "daily_bars"
        return default_freshness_validate(dataset, result, sla_key=sla, require_live=kwargs.get("require_live", False))

    def fetch(self, dataset: str, **kwargs: Any) -> FabricFetchResult:
        live_only = bool(kwargs.get("live_only"))
        require_live = bool(kwargs.get("require_live") or live_only)
        min_rows = kwargs.get("min_rows", 5000 if dataset == "spot_quotes" else 1)
        chain = self.provider_chain(
            dataset, live_only=live_only, provider_filter=kwargs.get("provider_filter"),
        )
        attempts: list[ProviderResult] = []
        live_successes: list[ProviderResult] = []
        winner: Optional[ProviderResult] = None
        selection_reason = "no provider succeeded"
        freshness_result: Optional[FreshnessValidationResult] = None

        for idx, name in enumerate(chain, start=1):
            provider = self.registry.get(name)
            if provider is None:
                attempts.append(ProviderResult(
                    provider=name, dataset=dataset, status=ProviderStatus.SKIPPED,
                    error="unknown provider", attempt=idx,
                ))
                continue
            if hasattr(provider, "configured") and not provider.configured():
                attempts.append(ProviderResult(
                    provider=name, dataset=dataset, status=ProviderStatus.NOT_CONFIGURED,
                    error="not configured", attempt=idx,
                ))
                continue
            result = provider.fetch(dataset, **kwargs)
            if result.attempt == 0:
                result = _copy_result(result, attempt=idx)
            attempts.append(result)
            if not result.ok:
                continue

            fv = self._freshness_check(provider, dataset, result, require_live=require_live)
            if not fv.passed or fv.blocked:
                attempts[-1] = _copy_result(
                    result, status=ProviderStatus.FAILED,
                    error=f"freshness gate: {fv.reason}",
                )
                continue

            if hasattr(provider, "quality_validate"):
                ok_q, q_errs = provider.quality_validate(dataset, result.payload)
            else:
                qr = run_snapshot_quality_checks(
                    dataset, result.payload, min_rows=min_rows,
                    provider=result.provider, source_dataset=result.source_dataset,
                )
                ok_q, q_errs = qr.passed, qr.errors
            if not ok_q:
                attempts[-1] = _copy_result(
                    result, status=ProviderStatus.FAILED, error=f"DQ: {'; '.join(q_errs)}",
                )
                continue

            if require_live and (result.is_manual or result.is_fixture or not result.is_live):
                attempts[-1] = _copy_result(
                    result, status=ProviderStatus.FAILED, error="live_only rejection",
                )
                continue

            if require_live and result.is_live:
                live_successes.append(result)

            if winner is None:
                winner = result
                freshness_result = fv
                selection_reason = f"first passing after freshness+DQ (attempt {idx}: {name})"

        cross_report = None
        quarantined = False
        if require_live and len(live_successes) >= 2:
            cross_report = reconcile_live_sources(dataset, live_successes, self._routing.get("cross_source", {}))
            if cross_report.get("quarantine"):
                quarantined = True
                winner = None
                selection_reason = "QUARANTINE_DATASET — cross-source tolerance exceeded"

        return FabricFetchResult(
            dataset=dataset, result=winner, attempts=attempts,
            selection_reason=selection_reason, freshness=freshness_result,
            cross_source=cross_report, quarantined=quarantined,
        )

    def fetch_market_snapshot(self, **kwargs: Any) -> dict[str, FabricFetchResult]:
        datasets = kwargs.get("datasets") or [
            "indices", "spot_quotes", "trading_calendar", "sector_boards", "security_master",
        ]
        return {ds: self.fetch(ds, **kwargs) for ds in datasets}


def build_registry_v2() -> dict[str, Any]:
    return _build_registry_v2()
