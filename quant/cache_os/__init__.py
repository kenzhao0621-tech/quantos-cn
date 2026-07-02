"""CacheOS — layered cache with per-data-type TTL, session awareness, honest freshness.

v2.2 spec (QuantOS_Domestic_Ashare_Advisory_Cache_Weights_v2_2_Prompt.md §2-3):
  L0 memory cache + L1 local disk cache + L3 feature cache + L4 prediction cache
  + L5 advisory cache, all keyed by a stable sha256 CacheKey and governed by
  CachePolicyRegistry (trading vs non-trading TTL).

Nothing in this package fabricates data; expired or missing entries are reported
as EXPIRED / UNAVAILABLE and the caller must degrade honestly.
"""

from quant.cache_os.cache_key import CacheKey, build_cache_key
from quant.cache_os.freshness import FreshnessStatus, evaluate_freshness
from quant.cache_os.policy import CachePolicyRegistry, get_policy_registry
from quant.cache_os.registry import CacheRegistry, get_cache_registry
from quant.cache_os.prediction_cache import PredictionCache, get_prediction_cache

__all__ = [
    "CacheKey",
    "build_cache_key",
    "FreshnessStatus",
    "evaluate_freshness",
    "CachePolicyRegistry",
    "get_policy_registry",
    "CacheRegistry",
    "get_cache_registry",
    "PredictionCache",
    "get_prediction_cache",
]
