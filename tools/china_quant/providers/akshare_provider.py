"""AKShare adapter — optional live/historical public data."""

from __future__ import annotations

from datetime import datetime

from tools.china_quant.providers.base import (
    BaseProvider,
    DataEnvelope,
    DataFreshness,
    ProviderError,
    SourceTrust,
)


class AKShareProvider(BaseProvider):
    name = "akshare"

    def __init__(self):
        try:
            import akshare  # noqa: F401
        except ImportError as e:
            raise ProviderError("akshare not installed", provider=self.name) from e

    def get_index_snapshot(self) -> DataEnvelope:
        import akshare as ak

        now = datetime.now()
        try:
            sh = ak.stock_zh_index_spot_em(symbol="上证指数")
            row = sh.iloc[0]
            payload = {
                "trade_date": now.strftime("%Y-%m-%d"),
                "sh_index_close": float(row["最新价"]),
                "sh_index_change_pct": float(row["涨跌幅"]),
                "data_timestamp": now.isoformat(),
                "source": "akshare",
            }
        except Exception as e:
            raise ProviderError(str(e), provider=self.name, retryable=True) from e
        return DataEnvelope(
            provider=self.name,
            payload=payload,
            retrieval_timestamp=now,
            market_timestamp=now,
            freshness=DataFreshness.DELAYED,
            source_id="akshare:index_spot",
            trust=SourceTrust.VERIFIED_DATA_PROVIDER,
            limitations=["Index only; delayed public feed"],
        )

    def get_universe(self) -> DataEnvelope:
        import akshare as ak

        now = datetime.now()
        try:
            df = ak.stock_info_a_code_name()
            stocks = [
                {"code": str(r["code"]), "name": str(r["name"]), "exchange": "SH" if str(r["code"]).startswith("6") else "SZ"}
                for _, r in df.iterrows()
            ]
        except Exception as e:
            raise ProviderError(str(e), provider=self.name, retryable=True) from e
        return DataEnvelope(
            provider=self.name,
            payload={"stocks": stocks, "count": len(stocks)},
            retrieval_timestamp=now,
            market_timestamp=now,
            freshness=DataFreshness.DELAYED,
            source_id="akshare:stock_info_a_code_name",
            limitations=["Listing metadata only; enrich locally"],
        )

    def get_daily_bars(self, code: str) -> DataEnvelope:
        import akshare as ak

        now = datetime.now()
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            bars = df.tail(120).to_dict(orient="records")
        except Exception as e:
            raise ProviderError(str(e), provider=self.name, retryable=True) from e
        return DataEnvelope(
            provider=self.name,
            payload={"code": code, "bars": bars},
            retrieval_timestamp=now,
            market_timestamp=now,
            freshness=DataFreshness.HISTORICAL,
            source_id=f"akshare:daily:{code}",
        )
