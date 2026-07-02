"""v2.2 §2.3 acceptance: cache key stability, sensitivity, uniqueness."""

from quant.cache_os.cache_key import CacheKey, build_cache_key, params_hash


def test_key_stable_across_ordering():
    a = build_cache_key({"symbol": "600519.SH", "data_type": "ohlcv_daily", "source": "tushare"})
    b = build_cache_key({"source": "tushare", "symbol": "600519.SH", "data_type": "ohlcv_daily"})
    assert a == b


def test_key_stable_for_nested_params_ordering():
    a = build_cache_key({"params": {"x": 1, "y": [1, 2]}, "k": "v"})
    b = build_cache_key({"k": "v", "params": {"y": [1, 2], "x": 1}})
    assert a == b


def test_key_changes_when_param_changes():
    base = {"symbol": "600519.SH", "data_type": "ohlcv_daily", "as_of_date": "2026-07-01"}
    other = dict(base, as_of_date="2026-07-02")
    assert build_cache_key(base) != build_cache_key(other)


def test_key_differs_by_symbol_source_data_type():
    k1 = CacheKey(data_type="ohlcv_daily", symbol="600519.SH", source="tushare").key()
    k2 = CacheKey(data_type="ohlcv_daily", symbol="000001.SZ", source="tushare").key()
    k3 = CacheKey(data_type="ohlcv_daily", symbol="600519.SH", source="akshare").key()
    k4 = CacheKey(data_type="realtime_quote", symbol="600519.SH", source="tushare").key()
    assert len({k1, k2, k3, k4}) == 4


def test_structured_key_normalizes_params():
    k1 = CacheKey(data_type="prediction", symbol="600519.SH", params={"h": 5, "n": 30})
    k2 = CacheKey(data_type="prediction", symbol="600519.SH", params={"n": 30, "h": 5})
    assert k1.key() == k2.key()
    assert k1.key() != CacheKey(data_type="prediction", symbol="600519.SH", params={"n": 31, "h": 5}).key()


def test_params_hash_int_float_equivalence():
    assert params_hash({"top_n": 25}) == params_hash({"top_n": 25.0})
    assert params_hash({"top_n": 25}) != params_hash({"top_n": 26})


def test_key_is_sha256_hex():
    key = build_cache_key({"a": 1})
    assert len(key) == 64
    int(key, 16)  # raises if not hex
