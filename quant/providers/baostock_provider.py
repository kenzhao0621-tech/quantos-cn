"""BaoStock historical daily bars adapter."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from quant.freshness_contract import FreshnessClass
from quant.provider_result import ProviderResult, ProviderStatus
from quant.providers.adapter_mixin import basic_quality, default_capabilities, default_freshness_validate, health_from_fetch


class BaoStockProvider:
    name = "baostock"

    def configured(self) -> bool:
        try:
            import baostock  # noqa: F401
            return True
        except ImportError:
            return False

    def capabilities(self):
        return default_capabilities(
            self.name,
            datasets={"daily_bars": "HISTORICAL", "historical_bars": "HISTORICAL", "trading_calendar": "HISTORICAL"},
            intraday=False,
            eod=True,
            historical=True,
            warnings=("Historical K-line only — not intraday live",),
        )

    def permission_probe(self) -> tuple[bool, str]:
        if not self.configured():
            return False, "baostock not installed"
        return True, "public historical API"

    def health_check(self, *, probe_live: bool = False):
        return health_from_fetch(self.name, configured=self.configured(), probe_live=probe_live, fetch_fn=self.fetch)

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        if not self.configured():
            return ProviderResult(
                provider=self.name, dataset=dataset, status=ProviderStatus.NOT_CONFIGURED,
                error="baostock not installed", retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        if dataset not in ("daily_bars", "historical_bars", "trading_calendar"):
            return ProviderResult(
                provider=self.name, dataset=dataset, status=ProviderStatus.SKIPPED,
                error=f"unsupported: {dataset}", retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        start = time.perf_counter()
        try:
            import baostock as bs

            bs.login()
            if dataset == "trading_calendar":
                rs = bs.query_trade_dates(start_date="2020-01-01", end_date=datetime.now().strftime("%Y-%m-%d"))
                days = []
                while rs.error_code == "0" and rs.next():
                    row = rs.get_row_data()
                    if row[1] == "1":
                        days.append(row[0])
                bs.logout()
                payload = {"days": days, "source_dataset": "query_trade_dates"}
                return ProviderResult(
                    provider=self.name, dataset=dataset, status=ProviderStatus.SUCCESS, payload=payload,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                    retrieved_at=datetime.now().isoformat(timespec="seconds"),
                    row_count=len(days), freshness=FreshnessClass.HISTORICAL.value,
                    endpoint="bs.query_trade_dates", source_dataset="query_trade_dates",
                    is_live=False, is_end_of_day=False,
                )
            code = kwargs.get("code", "sh.600000")
            start_date = kwargs.get("start_date", "2025-01-01")
            end_date = kwargs.get("end_date", datetime.now().strftime("%Y-%m-%d"))
            rs = bs.query_history_k_data_plus(
                code, "date,open,high,low,close,volume,amount",
                start_date=start_date, end_date=end_date, frequency="d", adjustflag="3",
            )
            bars = []
            while rs.error_code == "0" and rs.next():
                r = rs.get_row_data()
                bars.append({
                    "trade_date": r[0], "open": float(r[1] or 0), "high": float(r[2] or 0),
                    "low": float(r[3] or 0), "close": float(r[4] or 0),
                    "volume": float(r[5] or 0), "amount": float(r[6] or 0), "code": code,
                })
            bs.logout()
            payload = {"bars": bars, "code": code, "adjustment_mode": "raw"}
            return ProviderResult(
                provider=self.name, dataset=dataset, status=ProviderStatus.SUCCESS, payload=payload,
                elapsed_ms=(time.perf_counter() - start) * 1000,
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
                row_count=len(bars), freshness=FreshnessClass.HISTORICAL.value,
                endpoint="bs.query_history_k_data_plus", source_dataset="history_k_data",
                market_date=bars[-1]["trade_date"] if bars else "",
                is_live=False, is_end_of_day=True,
            )
        except Exception as e:
            return ProviderResult(
                provider=self.name, dataset=dataset, status=ProviderStatus.FAILED, error=str(e),
                elapsed_ms=(time.perf_counter() - start) * 1000,
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )

    def normalize(self, dataset: str, raw: Any) -> Any:
        return raw

    def quality_validate(self, dataset: str, payload: Any) -> tuple[bool, list[str]]:
        return basic_quality(dataset, payload, min_rows=1)

    def freshness_validate(self, dataset: str, result: ProviderResult, **kwargs: Any):
        return default_freshness_validate(dataset, result, sla_key="historical_bars", require_live=False)

    def persist(self, dataset: str, result: ProviderResult, *, run_id: str) -> None:
        return None
