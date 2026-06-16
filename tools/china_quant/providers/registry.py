"""Provider registry — strategy code uses registry, not raw AKShare."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from tools.china_quant.providers.base import BaseProvider, DataEnvelope, ProviderError
from tools.china_quant.providers.fixture_provider import FixtureProvider


class ProviderRegistry:
    def __init__(self, fixtures_dir: Path, *, use_akshare: bool = False):
        self.fixtures_dir = fixtures_dir
        self._fixture = FixtureProvider(fixtures_dir)
        self._akshare = None
        if use_akshare:
            try:
                from tools.china_quant.providers.akshare_provider import AKShareProvider
                self._akshare = AKShareProvider()
            except Exception:
                pass

    @property
    def fixture(self) -> FixtureProvider:
        return self._fixture

    def get_universe(self, *, mode: str = "fixture", name: str = "universe_full") -> DataEnvelope:
        if mode == "fixture":
            return self._fixture.load_universe(name)
        if mode == "akshare" and self._akshare:
            return self._akshare.get_universe()
        raise ProviderError(f"Universe unavailable for mode={mode}", provider="registry")

    def get_market_snapshot(self, *, mode: str = "fixture", name: str = "bullish_market") -> DataEnvelope:
        if mode == "fixture":
            return self._fixture.load_market_bundle(name)
        if mode == "akshare" and self._akshare:
            return self._akshare.get_index_snapshot()
        raise ProviderError(f"Snapshot unavailable for mode={mode}", provider="registry")

    def get_bars(self, code: str, *, mode: str = "fixture") -> DataEnvelope:
        if mode == "fixture":
            return self._fixture.load_bars(code)
        if mode == "akshare" and self._akshare:
            return self._akshare.get_daily_bars(code)
        raise ProviderError(f"Bars unavailable for {code}", provider="registry")
