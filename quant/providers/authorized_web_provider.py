"""Authorized public-web dataset ingestion."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from quant.freshness_contract import FreshnessClass
from quant.provider_result import ProviderResult, ProviderStatus
from quant.providers.adapter_mixin import default_capabilities, default_freshness_validate
from quant._config import CONFIG_DIR, load_config

ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = CONFIG_DIR / "authorized_data_targets.yaml"

_DEFAULT_ALLOWLIST = {
    "targets": [],
}


class AuthorizedWebDatasetProvider:
    name = "authorized_web"

    def configured(self) -> bool:
        return ALLOWLIST_PATH.exists() or (CONFIG_DIR / "authorized_data_targets.json").exists()

    def capabilities(self):
        return default_capabilities(
            self.name,
            datasets={"sector_membership": "HISTORICAL", "official_disclosures": "HISTORICAL"},
            warnings=("Only allowlisted public URLs",),
        )

    def permission_probe(self) -> tuple[bool, str]:
        cfg = load_config("authorized_data_targets", defaults=_DEFAULT_ALLOWLIST)
        if not cfg.get("targets"):
            return False, "no authorized targets configured"
        return True, f"{len(cfg['targets'])} allowlisted targets"

    def health_check(self, *, probe_live: bool = False):
        from quant.provider_base_v2 import ProviderHealth
        ok, msg = self.permission_probe()
        return ProviderHealth(
            provider_name=self.name, configured=self.configured(), reachable=ok,
            authenticated=None, status="READY" if ok else "NOT_CONFIGURED",
            latency_ms=None, capabilities=self.capabilities(),
            last_error_class=None, last_error_message=None if ok else msg,
            checked_at=datetime.now(),
        )

    def _allowed(self, url: str) -> bool:
        cfg = load_config("authorized_data_targets", defaults=_DEFAULT_ALLOWLIST)
        host = urlparse(url).netloc
        for t in cfg.get("targets", []):
            if host.endswith(t.get("host", "")) or url.startswith(t.get("prefix", "")):
                return True
        return False

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        url = kwargs.get("url", "")
        if not url:
            return ProviderResult(
                provider=self.name, dataset=dataset, status=ProviderStatus.SKIPPED,
                error="url required", retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        if not self._allowed(url):
            return ProviderResult(
                provider=self.name, dataset=dataset, status=ProviderStatus.FAILED,
                error="URL not on allowlist", retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        return ProviderResult(
            provider=self.name, dataset=dataset, status=ProviderStatus.SKIPPED,
            error="fetch requires explicit run with network — use official_file provider for local files",
            retrieved_at=datetime.now().isoformat(timespec="seconds"),
            freshness=FreshnessClass.SOURCE_LATEST_TIMESTAMP_UNCONFIRMED.value,
        )

    def normalize(self, dataset: str, raw: Any) -> Any:
        return raw

    def quality_validate(self, dataset: str, payload: Any) -> tuple[bool, list[str]]:
        return bool(payload), [] if payload else ["empty"]

    def freshness_validate(self, dataset: str, result: ProviderResult, **kwargs: Any):
        return default_freshness_validate(dataset, result, sla_key="official_disclosures", require_live=False)

    def persist(self, dataset: str, result: ProviderResult, *, run_id: str) -> None:
        return None
