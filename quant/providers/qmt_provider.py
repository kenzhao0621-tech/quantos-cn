"""QMT / MiniQMT read-only market data adapter — no order execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quant.freshness_contract import FreshnessClass
from quant.provider_result import ProviderResult, ProviderStatus
from quant.providers.adapter_mixin import default_capabilities, default_freshness_validate, health_from_fetch
from quant.secret_loader import configured


class QMTMarketDataProvider:
    name = "qmt_market_data"

    def configured(self) -> bool:
        return configured("QMT_DATA_PATH") or configured("MINIQMT_PATH")

    def capabilities(self):
        return default_capabilities(
            self.name,
            datasets={"live_spot": "BROKER_REALTIME", "live_indices": "BROKER_REALTIME", "minute_bars": "BROKER_REALTIME"},
            requires_credentials=True,
            intraday=True,
            warnings=("Read-only market data — order/trade modules disabled", "Requires local QMT/MiniQMT install"),
        )

    def permission_probe(self) -> tuple[bool, str]:
        if not self.configured():
            return False, "QMT_DATA_PATH or MINIQMT_PATH not set"
        return False, "QMT SDK not wired in this environment — NOT_CONFIGURED for live fetch"

    def health_check(self, *, probe_live: bool = False):
        return health_from_fetch(self.name, configured=self.configured(), probe_live=False, fetch_fn=self.fetch)

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        if not self.configured():
            return ProviderResult(
                provider=self.name, dataset=dataset, status=ProviderStatus.NOT_CONFIGURED,
                error="QMT path not configured", retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        return ProviderResult(
            provider=self.name, dataset=dataset, status=ProviderStatus.NOT_CONFIGURED,
            error="QMT read-only adapter requires local xtquant — not available in CI",
            retrieved_at=datetime.now().isoformat(timespec="seconds"),
            freshness=FreshnessClass.BROKER_REALTIME.value,
        )

    def normalize(self, dataset: str, raw: Any) -> Any:
        return raw

    def quality_validate(self, dataset: str, payload: Any) -> tuple[bool, list[str]]:
        return True, []

    def freshness_validate(self, dataset: str, result: ProviderResult, **kwargs: Any):
        return default_freshness_validate(dataset, result, sla_key="live_spot", require_live=kwargs.get("require_live", False))

    def persist(self, dataset: str, result: ProviderResult, *, run_id: str) -> None:
        return None
