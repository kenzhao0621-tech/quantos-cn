"""AKShare provider family — Eastmoney, split-board, and Sina backends."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable, Optional

from quant.provider_result import ProviderResult, ProviderStatus
from tools.china_quant.providers.akshare_provider import (
    AKShareProvider,
    _board_from_code,
)
from tools.china_quant.providers.base import ProviderError


class _AkshareBase:
    """Shared fetch wrapper for V4 provider results."""

    name: str = "akshare_base"

    def __init__(self) -> None:
        self._inner: Optional[AKShareProvider] = None

    def _provider(self) -> AKShareProvider:
        if self._inner is None:
            self._inner = AKShareProvider(use_cache=True)
        return self._inner

    def _timed(
        self,
        dataset: str,
        fn: Callable[[], DataEnvelope],
        *,
        attempt: int = 1,
    ) -> ProviderResult:
        start = time.perf_counter()
        try:
            env = fn()
            elapsed = (time.perf_counter() - start) * 1000
            payload = env.payload
            row_count = env.row_count
            if isinstance(payload, dict) and "rows" in payload:
                row_count = len(payload["rows"])
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.SUCCESS,
                payload=payload,
                attempt=attempt,
                elapsed_ms=round(elapsed, 2),
                retrieved_at=env.retrieval_timestamp.isoformat(timespec="seconds"),
                data_hash=env.data_hash,
                row_count=row_count,
                freshness=env.freshness.value if hasattr(env.freshness, "value") else str(env.freshness),
                limitations=tuple(env.limitations),
            )
        except ProviderError as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.FAILED,
                error=str(e),
                attempt=attempt,
                elapsed_ms=round(elapsed, 2),
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        except ImportError as e:
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.NOT_CONFIGURED,
                error=str(e),
                attempt=attempt,
                elapsed_ms=0.0,
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.FAILED,
                error=str(e),
                attempt=attempt,
                elapsed_ms=round(elapsed, 2),
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        dispatch = {
            "spot_quotes": lambda: self._provider().get_spot_quotes(),
            "indices": lambda: self._provider().get_indices(),
            "trading_calendar": lambda: self._provider().get_trading_calendar(),
            "sector_boards": lambda: self._provider().get_sector_boards(),
            "security_master": lambda: self._provider().get_security_master(),
        }
        if dataset not in dispatch:
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.SKIPPED,
                error=f"dataset not supported: {dataset}",
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        return self._timed(dataset, dispatch[dataset])


class AkshareEastmoneyProvider(_AkshareBase):
    name = "akshare_eastmoney"


class AkshareSinaProvider:
    """Sina spot via stock_zh_a_spot — never Eastmoney."""

    name = "akshare_sina"
    _last_fetch: float = 0.0
    _cache: dict[str, Any] | None = None
    _cache_ttl = 60
    _min_interval = 30

    def configured(self) -> bool:
        return True

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        if dataset == "spot_quotes":
            return self._fetch_spot(**kwargs)
        if dataset == "trading_calendar":
            base = _AkshareBase()
            base.name = self.name
            return base._timed(dataset, lambda: base._provider().get_trading_calendar())
        if dataset == "indices":
            return self._fetch_indices_sina()
        return ProviderResult(
            provider=self.name, dataset=dataset, status=ProviderStatus.SKIPPED,
            error=f"use other provider for {dataset}",
            retrieved_at=datetime.now().isoformat(timespec="seconds"),
        )

    def _fetch_spot(self, **kwargs: Any) -> ProviderResult:
        import hashlib
        import json
        import time as _time

        from quant.providers.sina_normalize import normalize_sina_spot

        now = _time.time()
        if self._cache and (now - self._last_fetch) < self._cache_ttl:
            payload = self._cache
            raw = json.dumps(payload, sort_keys=True, default=str)
            return ProviderResult(
                provider=self.name, dataset="spot_quotes", status=ProviderStatus.SUCCESS,
                payload=payload, elapsed_ms=0.0,
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
                data_hash=hashlib.sha256(raw.encode()).hexdigest()[:16],
                row_count=len(payload.get("rows", [])),
                freshness=payload.get("freshness", ""),
                endpoint="ak.stock_zh_a_spot", source_dataset="stock_zh_a_spot",
                market_date=payload.get("market_date") or "",
                is_live=True, is_end_of_day=False,
            )
        if self._last_fetch and (now - self._last_fetch) < self._min_interval:
            return ProviderResult(
                provider=self.name, dataset="spot_quotes", status=ProviderStatus.FAILED,
                error="rate limit: minimum interval not elapsed",
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        start = _time.perf_counter()
        try:
            import akshare as ak

            raw_df = ak.stock_zh_a_spot()
            payload, _report = normalize_sina_spot(raw_df)
            elapsed = (_time.perf_counter() - start) * 1000
            self._cache = payload
            self._last_fetch = _time.time()
            raw = json.dumps(payload, sort_keys=True, default=str)
            return ProviderResult(
                provider=self.name, dataset="spot_quotes", status=ProviderStatus.SUCCESS,
                payload=payload, elapsed_ms=round(elapsed, 2),
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
                data_hash=hashlib.sha256(raw.encode()).hexdigest()[:16],
                row_count=len(payload.get("rows", [])),
                freshness=payload.get("freshness", ""),
                limitations=("Sina stock_zh_a_spot; not Eastmoney",),
                endpoint="ak.stock_zh_a_spot", source_dataset="stock_zh_a_spot",
                market_date=payload.get("market_date") or "",
                is_live=True, is_end_of_day=False,
            )
        except Exception as e:
            elapsed = (_time.perf_counter() - start) * 1000
            return ProviderResult(
                provider=self.name, dataset="spot_quotes", status=ProviderStatus.FAILED,
                error=str(e), elapsed_ms=round(elapsed, 2),
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
                endpoint="ak.stock_zh_a_spot", source_dataset="stock_zh_a_spot",
            )

    def _fetch_indices_sina(self) -> ProviderResult:
        start = time.perf_counter()
        try:
            import akshare as ak
            import hashlib
            import json

            df = ak.stock_zh_index_daily(symbol="sh000001")
            last = df.iloc[-1]
            close_col = "close" if "close" in df.columns else df.columns[-1]
            payload = {
                "sh": {"close": float(last[close_col]), "name": "上证指数", "source": "sina_daily"},
                "source_dataset": "stock_zh_index_daily",
                "endpoint": "ak.stock_zh_index_daily",
            }
            elapsed = (time.perf_counter() - start) * 1000
            raw = json.dumps(payload, sort_keys=True, default=str)
            return ProviderResult(
                provider=self.name, dataset="indices", status=ProviderStatus.SUCCESS,
                payload=payload, elapsed_ms=round(elapsed, 2),
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
                data_hash=hashlib.sha256(raw.encode()).hexdigest()[:16],
                freshness="DELAYED",
                limitations=("Sina daily bar — partial index set",),
                endpoint="ak.stock_zh_index_daily", source_dataset="stock_zh_index_daily",
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ProviderResult(
                provider=self.name, dataset="indices", status=ProviderStatus.FAILED,
                error=str(e), elapsed_ms=round(elapsed, 2),
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )


class AkshareSplitMarketProvider(_AkshareBase):
    """Fetch SH / SZ / BJ boards separately and merge rows."""

    name = "akshare_split"

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        if dataset != "spot_quotes":
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.SKIPPED,
                error="split provider only supports spot_quotes",
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        start = time.perf_counter()
        try:
            import akshare as ak

            segments: list[tuple[str, Callable[[], Any]]] = [
                ("SH", lambda: ak.stock_sh_a_spot_em()),
                ("SZ", lambda: ak.stock_sz_a_spot_em()),
                ("BJ", lambda: ak.stock_bj_a_spot_em()),
            ]
            merged: list[dict[str, Any]] = []
            errors: list[str] = []
            for label, fn in segments:
                try:
                    df = fn()
                    for _, r in df.iterrows():
                        code = str(r.get("代码", r.get("code", ""))).zfill(6)
                        name = str(r.get("名称", r.get("name", "")))
                        price = r.get("最新价", r.get("price", 0))
                        chg = r.get("涨跌幅", r.get("change_pct", 0))
                        merged.append({
                            "code": code,
                            "name": name,
                            "price": float(price) if price == price else 0.0,
                            "change_pct": float(chg) if chg == chg else 0.0,
                            "amount": float(r.get("成交额", 0) or 0),
                            "volume": float(r.get("成交量", 0) or 0),
                            "exchange": label if label != "BJ" else "BJ",
                            "board": _board_from_code(code),
                            "is_st": "ST" in name,
                            "segment": label,
                        })
                except Exception as seg_err:
                    errors.append(f"{label}: {seg_err}")

            elapsed = (time.perf_counter() - start) * 1000
            if not merged:
                return ProviderResult(
                    provider=self.name,
                    dataset=dataset,
                    status=ProviderStatus.EMPTY,
                    error="; ".join(errors) or "no rows from any segment",
                    elapsed_ms=round(elapsed, 2),
                    retrieved_at=datetime.now().isoformat(timespec="seconds"),
                )
            payload = {"rows": merged, "segments": [s[0] for s in segments], "segment_errors": errors}
            from tools.china_quant.providers.base import DataFreshness
            import hashlib
            import json

            raw = json.dumps(payload, sort_keys=True, default=str)
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.SUCCESS,
                payload=payload,
                elapsed_ms=round(elapsed, 2),
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
                data_hash=hashlib.sha256(raw.encode()).hexdigest()[:16],
                row_count=len(merged),
                freshness=DataFreshness.DELAYED.value,
                limitations=("Merged SH/SZ/BJ segments",),
            )
        except ImportError as e:
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.NOT_CONFIGURED,
                error=str(e),
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
