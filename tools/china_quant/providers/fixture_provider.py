"""Fixture provider for deterministic full-universe tests."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.china_quant.providers.base import (
    BaseProvider,
    DataEnvelope,
    DataFreshness,
    ProviderError,
    SourceTrust,
)


class FixtureProvider(BaseProvider):
    name = "fixture"

    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = fixtures_dir

    def _load(self, name: str) -> dict[str, Any]:
        path = self.fixtures_dir / f"{name}.json"
        if not path.exists():
            raise ProviderError(f"Fixture missing: {name}", provider=self.name)
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    def load_universe(self, name: str = "universe_full") -> DataEnvelope:
        data = self._load(name)
        ts = datetime.fromisoformat(data.get("data_timestamp", "2026-06-12T15:00:00"))
        return DataEnvelope(
            provider=self.name,
            payload=data,
            retrieval_timestamp=datetime.now(),
            market_timestamp=ts,
            freshness=DataFreshness.FIXTURE,
            source_id=f"fixture:{name}",
            trust=SourceTrust.VERIFIED_DATA_PROVIDER,
            limitations=["SAMPLE_FIXTURE — not live market data"],
        )

    def load_market_bundle(self, name: str) -> DataEnvelope:
        data = self._load(name)
        ts = datetime.fromisoformat(data["data_timestamp"])
        return DataEnvelope(
            provider=self.name,
            payload=data,
            retrieval_timestamp=datetime.now(),
            market_timestamp=ts,
            freshness=DataFreshness.FIXTURE,
            source_id=f"fixture:{name}",
            limitations=[data.get("fixture_label", "fixture")],
        )

    def load_bars(self, code: str) -> DataEnvelope:
        path = self.fixtures_dir / "bars" / f"{code}.json"
        if not path.exists():
            raise ProviderError(f"No bar fixture for {code}", provider=self.name)
        data = json.loads(path.read_text(encoding="utf-8"))
        return DataEnvelope(
            provider=self.name,
            payload=data,
            retrieval_timestamp=datetime.now(),
            market_timestamp=datetime.fromisoformat(data["end_date"] + "T15:00:00"),
            freshness=DataFreshness.HISTORICAL,
            source_id=f"fixture:bars/{code}",
        )

    def load_policy(self) -> DataEnvelope:
        data = self._load("policy_items")
        return DataEnvelope(
            provider=self.name,
            payload=data,
            retrieval_timestamp=datetime.now(),
            market_timestamp=datetime.now(),
            freshness=DataFreshness.FIXTURE,
            source_id="fixture:policy_items",
            trust=SourceTrust.OFFICIAL_SECONDARY,
        )

    def load_institutional(self) -> DataEnvelope:
        data = self._load("institutional_signals")
        return DataEnvelope(
            provider=self.name,
            payload=data,
            retrieval_timestamp=datetime.now(),
            market_timestamp=datetime.now(),
            freshness=DataFreshness.FIXTURE,
            source_id="fixture:institutional_signals",
        )
