"""Expanded AKShare provider with cache, retry, and full interfaces."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from tools.china_quant.cache import cache_get, cache_key, cache_set
from tools.china_quant.providers.base import (
    DataEnvelope,
    DataFreshness,
    ProviderError,
    SourceTrust,
)

TIMEOUT_SEC = 45
MAX_RETRIES = 2
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "china-quant"


def _board_from_code(code: str) -> str:
    c = str(code).zfill(6)
    if c.startswith("688"):
        return "STAR"
    if c.startswith("300"):
        return "CHINEXT"
    if c.startswith(("43", "83", "87", "92")):
        return "BSE"
    if c.startswith("6"):
        return "MAIN_SH"
    return "MAIN_SZ"


def _exchange_from_code(code: str) -> str:
    b = _board_from_code(code)
    if b in ("MAIN_SH", "STAR"):
        return "SH"
    if b == "BSE":
        return "BJ"
    return "SZ"


class AKShareProvider:
    name = "akshare"

    def __init__(self, cache_dir: Path = CACHE_DIR, use_cache: bool = True):
        try:
            import akshare  # noqa: F401
        except ImportError as e:
            raise ProviderError("akshare not installed — use .venv-china-quant", provider=self.name) from e
        self.cache_dir = cache_dir
        self.use_cache = use_cache

    def _call(self, source_id: str, fn: Callable[[], Any], *, ttl: int = 30) -> Any:
        key = cache_key(source_id)
        if self.use_cache:
            hit = cache_get(self.cache_dir, key, ttl)
            if hit is not None:
                return hit
        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                result = fn()
                if result is None or (hasattr(result, "__len__") and len(result) == 0):
                    raise ProviderError("empty response", provider=self.name, retryable=True)
                if self.use_cache:
                    to_store = result.to_dict(orient="records") if hasattr(result, "to_dict") else result
                    cache_set(self.cache_dir, key, to_store)
                return result
            except ProviderError:
                raise
            except Exception as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    time.sleep(1.5 * (attempt + 1))
        raise ProviderError(str(last_err), provider=self.name, retryable=True) from last_err

    def _env(
        self,
        source_id: str,
        payload: Any,
        *,
        freshness: DataFreshness,
        market_ts: Optional[datetime] = None,
        limitations: Optional[list[str]] = None,
        row_count: int = 0,
        missing: Optional[list[str]] = None,
    ) -> DataEnvelope:
        now = datetime.now()
        if isinstance(payload, list):
            row_count = row_count or len(payload)
        elif isinstance(payload, dict) and "rows" in payload:
            row_count = len(payload["rows"])
        return DataEnvelope(
            provider=self.name,
            payload=payload,
            retrieval_timestamp=now,
            market_timestamp=market_ts or now,
            freshness=freshness,
            source_id=source_id,
            trust=SourceTrust.VERIFIED_DATA_PROVIDER,
            limitations=limitations or [],
            row_count=row_count,
            missing_fields=missing or [],
        )

    def get_trading_calendar(self) -> DataEnvelope:
        import akshare as ak

        def fetch():
            df = ak.tool_trade_date_hist_sina()
            return df["trade_date"].astype(str).tolist()

        days = self._call("tool_trade_date_hist_sina", fetch, ttl=1440)
        return self._env("akshare:calendar", {"days": days}, freshness=DataFreshness.HISTORICAL, row_count=len(days))

    def get_market_session_state(self) -> DataEnvelope:
        now = datetime.now()
        h, m = now.hour, now.minute
        t = h * 60 + m
        if t < 9 * 60 + 30:
            state = "PRE_OPEN"
        elif t < 11 * 60 + 30 or (13 * 60 <= t < 15 * 60):
            state = "TRADING"
        elif t < 13 * 60:
            state = "LUNCH"
        else:
            state = "CLOSED"
        fresh = DataFreshness.LIVE_OR_DELAYED if state == "TRADING" else DataFreshness.PREVIOUS_CLOSE
        return self._env("akshare:session", {"state": state, "now": now.isoformat()}, freshness=fresh)

    def get_indices(self) -> DataEnvelope:
        import akshare as ak

        def fetch():
            df = ak.stock_zh_index_spot_em()
            name_col = "名称" if "名称" in df.columns else "name"
            price_col = "最新价" if "最新价" in df.columns else "close"
            chg_col = "涨跌幅" if "涨跌幅" in df.columns else "change"
            mapping = {"上证指数": "sh", "深证成指": "sz", "创业板指": "cyb", "科创50": "star"}
            out = {}
            for cn, key in mapping.items():
                rows = df[df[name_col] == cn]
                if rows.empty:
                    continue
                row = rows.iloc[0]
                out[key] = {"close": float(row[price_col]), "change_pct": float(row[chg_col]), "name": cn}
            if not out:
                raise ProviderError("index rows missing from spot table", provider=self.name)
            return out

        data = self._call("index_spot_table", fetch, ttl=5)
        return self._env("akshare:indices", data, freshness=DataFreshness.DELAYED, limitations=["Public delayed feed"])

    def get_index_history(self, symbol: str = "000001", end_date: Optional[str] = None) -> DataEnvelope:
        import akshare as ak

        def fetch():
            df = ak.stock_zh_index_daily_em(symbol=symbol)
            date_col = "date" if "date" in df.columns else ("日期" if "日期" in df.columns else df.columns[0])
            if end_date:
                df = df[df[date_col].astype(str) <= end_date.replace("-", "")]
            return df.tail(120).to_dict(orient="records")

        rows = self._call(f"index_hist:{symbol}:{end_date}", fetch, ttl=60)
        return self._env(f"akshare:index_hist:{symbol}", {"rows": rows}, freshness=DataFreshness.HISTORICAL, row_count=len(rows))

    def get_security_master(self) -> DataEnvelope:
        import akshare as ak

        def fetch():
            df = ak.stock_info_a_code_name()
            return [{"code": str(r["code"]).zfill(6), "name": str(r["name"])} for _, r in df.iterrows()]

        rows = self._call("stock_info_a_code_name", fetch, ttl=1440)
        return self._env("akshare:security_master", {"rows": rows}, freshness=DataFreshness.DELAYED, row_count=len(rows))

    def get_spot_quotes(self) -> DataEnvelope:
        import akshare as ak

        def fetch():
            df = ak.stock_zh_a_spot_em()
            cols = list(df.columns)
            required = ["代码", "名称", "最新价", "涨跌幅", "成交额", "成交量"]
            missing = [c for c in required if c not in cols]
            if missing:
                raise ProviderError(f"schema change missing {missing}", provider=self.name)
            rows = []
            for _, r in df.iterrows():
                code = str(r["代码"]).zfill(6)
                name = str(r["名称"])
                rows.append({
                    "code": code,
                    "name": name,
                    "price": float(r["最新价"]) if r["最新价"] == r["最新价"] else 0,
                    "change_pct": float(r["涨跌幅"]) if r["涨跌幅"] == r["涨跌幅"] else 0,
                    "amount": float(r["成交额"]) if r["成交额"] == r["成交额"] else 0,
                    "volume": float(r["成交量"]) if r["成交量"] == r["成交量"] else 0,
                    "exchange": _exchange_from_code(code),
                    "board": _board_from_code(code),
                    "is_st": "ST" in name or "*ST" in name,
                })
            return {"rows": rows, "missing": missing}

        data = self._call("stock_zh_a_spot_em", fetch, ttl=3)
        fresh = DataFreshness.DELAYED
        sess = self.get_market_session_state().payload.get("state")
        if sess == "TRADING":
            fresh = DataFreshness.REAL_TIME
        return self._env(
            "akshare:spot",
            data,
            freshness=fresh,
            row_count=len(data["rows"]),
            missing=data.get("missing"),
            limitations=["Full-market spot; delayed during session"],
        )

    def get_daily_bars(self, code: str, end_date: Optional[str] = None, adjust: str = "qfq") -> DataEnvelope:
        import akshare as ak

        def fetch():
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust=adjust)
            if end_date:
                df = df[df["日期"].astype(str) <= end_date]
            return df.tail(120).to_dict(orient="records")

        rows = self._call(f"bars:{code}:{end_date}:{adjust}", fetch, ttl=60)
        return self._env(f"akshare:bars:{code}", {"code": code, "bars": rows}, freshness=DataFreshness.HISTORICAL, row_count=len(rows))

    def get_sector_boards(self) -> DataEnvelope:
        import akshare as ak

        def fetch():
            df = ak.stock_board_industry_name_em()
            return df.to_dict(orient="records")

        rows = self._call("stock_board_industry_name_em", fetch, ttl=30)
        return self._env("akshare:sector_boards", {"rows": rows}, freshness=DataFreshness.DELAYED, row_count=len(rows))

    def get_stock_individual_info(self, code: str) -> DataEnvelope:
        import akshare as ak

        def fetch():
            df = ak.stock_individual_info_em(symbol=code)
            return dict(zip(df["item"], df["value"]))

        info = self._call(f"individual_info:{code}", fetch, ttl=1440)
        return self._env(f"akshare:info:{code}", info, freshness=DataFreshness.DELAYED)
