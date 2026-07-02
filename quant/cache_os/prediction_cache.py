"""Generic model prediction cache (L4) — keyed by (model, symbol, horizon, data_version).

Designed for Kronos but model-agnostic: any predictor (Kronos mini/small, LGBM
ensemble, statistical fallback) caches through here. ``data_version`` should be
the fingerprint of the underlying bars (see quant.compute_os.incremental), so a
new K-line automatically invalidates the prediction without any TTL guesswork,
while TTL still bounds staleness during trading hours (v2.2 §3.3
kronos_prediction: 600s trading / 3600s non-trading).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from quant.cache_os.cache_key import CacheKey
from quant.cache_os.registry import CacheRegistry, CacheResult, get_cache_registry


class PredictionCache:
    DATA_TYPE = "kronos_prediction"

    def __init__(self, registry: Optional[CacheRegistry] = None) -> None:
        self.registry = registry or get_cache_registry()

    def _key(
        self,
        *,
        model: str,
        symbol: str,
        horizon: str,
        data_version: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> CacheKey:
        return CacheKey(
            data_type=self.DATA_TYPE,
            symbol=symbol,
            source=model,
            frequency=str(horizon),
            as_of_date=data_version,
            params=dict(params or {}),
        )

    def get_or_predict(
        self,
        *,
        model: str,
        symbol: str,
        horizon: str,
        data_version: str,
        predictor: Callable[[], Any],
        params: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False,
    ) -> CacheResult:
        """Return cached prediction unless the underlying data_version changed.

        The predictor result should be a dict carrying at least direction /
        expected_return / confidence and MUST include its own uncertainty
        fields — CacheOS never invents them.
        """
        key = self._key(model=model, symbol=symbol, horizon=horizon,
                        data_version=data_version, params=params)
        return self.registry.get_or_compute(
            key, predictor, persist=True, force_refresh=force_refresh,
        )

    def peek(
        self,
        *,
        model: str,
        symbol: str,
        horizon: str,
        data_version: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[CacheResult]:
        key = self._key(model=model, symbol=symbol, horizon=horizon,
                        data_version=data_version, params=params)
        return self.registry.peek(key, persist=True)


_cache: Optional[PredictionCache] = None


def get_prediction_cache() -> PredictionCache:
    global _cache
    if _cache is None:
        _cache = PredictionCache()
    return _cache
