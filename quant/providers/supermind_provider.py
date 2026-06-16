"""Supermind provider — requires SUPERMIND_API_KEY env."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

from quant.provider_result import ProviderResult, ProviderStatus


class SupermindProvider:
    name = "supermind"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or os.environ.get("SUPERMIND_API_KEY", "")).strip()

    def configured(self) -> bool:
        return bool(self.api_key)

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        if not self.configured():
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.NOT_CONFIGURED,
                error="SUPERMIND_API_KEY not set",
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        return ProviderResult(
            provider=self.name,
            dataset=dataset,
            status=ProviderStatus.SKIPPED,
            error="Supermind SDK integration stub — configure client separately",
            retrieved_at=datetime.now().isoformat(timespec="seconds"),
        )
