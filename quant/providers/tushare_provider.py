"""Tushare production provider — token from env/.env.local only."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from quant.provider_result import ProviderResult, ProviderStatus
from quant.providers.tushare_daily_adapter import normalize_tushare_daily
from quant.secret_loader import configured, get


class TushareProvider:
    name = "tushare"
    _cal_cache: str = ""
    _cal_cache_at: float = 0.0

    def configured(self) -> bool:
        return configured("TUSHARE_TOKEN")

    def _pro(self):
        import tushare as ts

        return ts.pro_api(get("TUSHARE_TOKEN"))

    def _result(
        self,
        dataset: str,
        *,
        status: ProviderStatus,
        payload: Any = None,
        error: str | None = None,
        elapsed_ms: float = 0.0,
        row_count: int = 0,
        freshness: str = "",
        limitations: tuple[str, ...] = (),
        endpoint: str = "",
        source_dataset: str = "",
        market_date: str = "",
        is_live: bool = False,
        is_end_of_day: bool = False,
    ) -> ProviderResult:
        prov = payload.get("provenance", {}) if isinstance(payload, dict) else {}
        return ProviderResult(
            provider=self.name,
            dataset=dataset,
            status=status,
            payload=payload,
            error=error,
            elapsed_ms=round(elapsed_ms, 2),
            retrieved_at=datetime.now().isoformat(timespec="seconds"),
            row_count=row_count or (len(payload.get("rows", [])) if isinstance(payload, dict) else 0),
            freshness=freshness or (payload.get("freshness", "") if isinstance(payload, dict) else ""),
            limitations=limitations or ("Licensed Tushare API",),
            endpoint=endpoint,
            source_dataset=source_dataset,
            market_date=market_date or (payload.get("market_date", "") if isinstance(payload, dict) else ""),
            is_live=is_live,
            is_end_of_day=is_end_of_day,
            is_manual=False,
            is_fixture=False,
        )

    def _heuristic_trade_date(self) -> str:
        now = datetime.now()
        d = now
        if now.hour < 16:
            d = now - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d.strftime("%Y%m%d")

    def _latest_completed_trade_date(self, pro) -> str:
        now_ts = time.time()
        if self._cal_cache and (now_ts - self._cal_cache_at) < 60:
            return self._cal_cache
        today = datetime.now().strftime("%Y%m%d")
        try:
            cal = pro.trade_cal(
                exchange="SSE",
                start_date=(datetime.now() - timedelta(days=14)).strftime("%Y%m%d"),
                end_date=today,
            )
            open_days = cal[cal["is_open"] == 1]["cal_date"].astype(str).tolist()
            if not open_days:
                return self._heuristic_trade_date()
            now = datetime.now()
            if now.hour < 16 and len(open_days) >= 2:
                candidates = [d for d in open_days if d <= today]
                if today in candidates and now.hour < 16:
                    candidates = [d for d in candidates if d < today] or candidates
                result = candidates[-1] if candidates else open_days[-1]
            else:
                result = open_days[-1]
            self._cal_cache = result
            self._cal_cache_at = now_ts
            return result
        except Exception as e:
            err = str(e)
            if "频率超限" in err or "rate" in err.lower() or "limit" in err.lower():
                return self._heuristic_trade_date()
            raise

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        if not self.configured():
            return self._result(dataset, status=ProviderStatus.NOT_CONFIGURED, error="TUSHARE_TOKEN not set")
        start = time.perf_counter()
        try:
            pro = self._pro()
            if dataset == "trading_calendar":
                df = pro.trade_cal(exchange="SSE", start_date="19900101", end_date="20261231")
                days = df[df["is_open"] == 1]["cal_date"].astype(str).tolist()
                payload = {"days": days, "source_dataset": "trade_cal", "endpoint": "pro.trade_cal"}
                return self._result(
                    dataset, status=ProviderStatus.SUCCESS, payload=payload,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                    endpoint="pro.trade_cal", source_dataset="trade_cal", freshness="HISTORICAL",
                )
            if dataset == "security_master":
                df = pro.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,exchange,list_date,industry")
                rows = [
                    {"code": str(r["symbol"]).zfill(6), "name": r["name"], "ts_code": r["ts_code"],
                     "exchange": r.get("exchange", ""), "list_date": str(r.get("list_date", "")),
                     "industry": r.get("industry", "")}
                    for _, r in df.iterrows()
                ]
                payload = {"rows": rows, "source_dataset": "stock_basic", "endpoint": "pro.stock_basic"}
                return self._result(
                    dataset, status=ProviderStatus.SUCCESS, payload=payload,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                    endpoint="pro.stock_basic", source_dataset="stock_basic",
                )
            if dataset == "spot_quotes":
                trade_date = kwargs.get("trade_date") or self._latest_completed_trade_date(pro)
                df = pro.daily(trade_date=trade_date)
                raw_rows = df.to_dict(orient="records")
                if not raw_rows:
                    return self._result(
                        dataset, status=ProviderStatus.EMPTY, error=f"empty daily for {trade_date}",
                        elapsed_ms=(time.perf_counter() - start) * 1000,
                    )
                payload = normalize_tushare_daily(raw_rows, trade_date=trade_date)
                return self._result(
                    dataset, status=ProviderStatus.SUCCESS, payload=payload,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                    endpoint="pro.daily", source_dataset="daily",
                    market_date=payload.get("market_date", ""),
                    is_live=False, is_end_of_day=True, freshness="END_OF_DAY",
                )
            return self._result(
                dataset, status=ProviderStatus.SKIPPED, error=f"dataset not supported: {dataset}",
            )
        except ImportError:
            return self._result(dataset, status=ProviderStatus.NOT_CONFIGURED, error="tushare not installed")
        except Exception as e:
            err = str(e)
            if "权限" in err or "permission" in err.lower():
                st = ProviderStatus.NOT_CONFIGURED
            else:
                st = ProviderStatus.FAILED
            return self._result(
                dataset, status=st, error=err,
                elapsed_ms=(time.perf_counter() - start) * 1000,
            )
