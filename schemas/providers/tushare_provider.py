"""Tushare provider — requires TUSHARE_TOKEN env."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

from quant.provider_result import ProviderResult, ProviderStatus


class TushareProvider:
    name = "tushare"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get("TUSHARE_TOKEN", "").strip()

    def configured(self) -> bool:
        return bool(self.token)

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        if not self.configured():
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.NOT_CONFIGURED,
                error="TUSHARE_TOKEN not set",
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        start = time.perf_counter()
        try:
            import tushare as ts

            pro = ts.pro_api(self.token)
            if dataset == "security_master":
                df = pro.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name")
                rows = [
                    {"code": str(r["symbol"]).zfill(6), "name": r["name"], "ts_code": r["ts_code"]}
                    for _, r in df.iterrows()
                ]
                payload = {"rows": rows}
            elif dataset == "spot_quotes":
                df = pro.daily(trade_date=kwargs.get("trade_date", datetime.now().strftime("%Y%m%d")))
                rows = df.to_dict(orient="records")
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
                limitations=("Licensed Tushare API",),
            )
        except ImportError:
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.NOT_CONFIGURED,
                error="tushare package not installed",
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
