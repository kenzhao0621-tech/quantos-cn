"""JQData (聚宽) provider — requires JQDATA_USER / JQDATA_PASSWORD env."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

from quant.provider_result import ProviderResult, ProviderStatus


class JQDataProvider:
    name = "jqdata"

    def __init__(self, user: str | None = None, password: str | None = None) -> None:
        self.user = (user or os.environ.get("JQDATA_USER", "")).strip()
        self.password = (password or os.environ.get("JQDATA_PASSWORD", "")).strip()

    def configured(self) -> bool:
        return bool(self.user and self.password)

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        if not self.configured():
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.NOT_CONFIGURED,
                error="JQDATA_USER / JQDATA_PASSWORD not set",
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        start = time.perf_counter()
        try:
            from jqdatasdk import auth, get_all_securities

            auth(self.user, self.password)
            if dataset == "security_master":
                df = get_all_securities(types=["stock"], date=None)
                rows = [
                    {"code": idx[:6], "name": str(row["display_name"])}
                    for idx, row in df.iterrows()
                ]
                payload = {"rows": rows}
            else:
                return ProviderResult(
                    provider=self.name,
                    dataset=dataset,
                    status=ProviderStatus.SKIPPED,
                    error=f"dataset not supported: {dataset}",
                    retrieved_at=datetime.now().isoformat(timespec="seconds"),
                )
            elapsed = (time.perf_counter() - start) * 1000
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.SUCCESS,
                payload=payload,
                elapsed_ms=round(elapsed, 2),
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
                row_count=len(payload.get("rows", [])),
                limitations=("JQData licensed API",),
            )
        except ImportError:
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.NOT_CONFIGURED,
                error="jqdatasdk package not installed",
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.FAILED,
                error=str(e),
                elapsed_ms=round(elapsed, 2),
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
