"""RQData (RiceQuant) adapter — licensed real-time/historical when configured."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from quant.freshness_contract import FreshnessClass
from quant.provider_result import ProviderResult, ProviderStatus
from quant.providers.adapter_mixin import (
    basic_quality,
    default_capabilities,
    default_freshness_validate,
    health_from_fetch,
)
from quant.secret_loader import configured, get


class RQDataProvider:
    name = "rqdata"

    def configured(self) -> bool:
        return configured("RQDATAC_LICENSE") or configured("RQDATA_LICENSE")

    def capabilities(self):
        return default_capabilities(
            self.name,
            datasets={
                "live_spot": "LICENSED_REALTIME",
                "index_daily": "LICENSED_REALTIME",
                "daily_bars": "END_OF_DAY",
                "fundamentals": "HISTORICAL",
            },
            requires_credentials=True,
            intraday=True,
            eod=True,
            historical=True,
            warnings=("Requires RiceQuant account and rqdatac package",),
        )

    def permission_probe(self) -> tuple[bool, str]:
        if not self.configured():
            return False, "RQDATAC_LICENSE not set"
        try:
            import rqdatac  # type: ignore
            rqdatac.init(get("RQDATAC_LICENSE") or get("RQDATA_LICENSE"))
            return True, "authenticated"
        except ImportError:
            return False, "rqdatac not installed"
        except Exception as e:
            return False, str(e)

    def health_check(self, *, probe_live: bool = False):
        return health_from_fetch(self.name, configured=self.configured(), probe_live=probe_live, fetch_fn=self.fetch)

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        if not self.configured():
            return self._result(dataset, ProviderStatus.NOT_CONFIGURED, error="RQDATAC_LICENSE not set")
        ok, msg = self.permission_probe()
        if not ok:
            return self._result(dataset, ProviderStatus.NOT_CONFIGURED, error=msg)
        return self._result(dataset, ProviderStatus.SKIPPED, error=f"dataset {dataset} not yet wired — use fallback chain")

    def normalize(self, dataset: str, raw: Any) -> Any:
        return raw

    def quality_validate(self, dataset: str, payload: Any) -> tuple[bool, list[str]]:
        return basic_quality(dataset, payload)

    def freshness_validate(self, dataset: str, result: ProviderResult, **kwargs: Any):
        sla = "live_spot" if dataset == "spot_quotes" else "daily_bars"
        return default_freshness_validate(dataset, result, sla_key=sla, require_live=kwargs.get("require_live", False))

    def persist(self, dataset: str, result: ProviderResult, *, run_id: str) -> None:
        return None

    def _result(self, dataset: str, status: ProviderStatus, **kw) -> ProviderResult:
        return ProviderResult(
            provider=self.name, dataset=dataset, status=status,
            retrieved_at=datetime.now().isoformat(timespec="seconds"),
            freshness=FreshnessClass.LICENSED_REALTIME.value if status == ProviderStatus.SUCCESS else "",
            **{k: v for k, v in kw.items() if k in ("payload", "error", "elapsed_ms", "row_count")},
        )
