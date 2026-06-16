"""Local snapshot provider for deterministic tests."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from quant.disclosures.protocol import (
    DisclosureCapabilities,
    DisclosureFetchResult,
    DisclosureProviderHealth,
    DisclosureStatus,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "docs" / "test-fixtures" / "disclosures" / "sample_announcements.json"


class LocalDisclosureSnapshotProvider:
    name = "local_snapshot"
    source_class = "LOCAL_TEST_FIXTURE"

    def health_check(self) -> DisclosureProviderHealth:
        return DisclosureProviderHealth(
            provider_name=self.name,
            configured=FIXTURE.exists(),
            reachable=FIXTURE.exists(),
            status="READY" if FIXTURE.exists() else "NOT_CONFIGURED",
            checked_at=datetime.now().isoformat(timespec="seconds"),
        )

    def capabilities(self) -> DisclosureCapabilities:
        return DisclosureCapabilities(
            provider_name=self.name,
            exchanges=["SSE", "SZSE", "BSE"],
            supports_symbol_filter=True,
            supports_category_filter=False,
            max_page_size=100,
        )

    def fetch_announcements(
        self,
        start_time: datetime,
        end_time: datetime,
        symbols: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
    ) -> DisclosureFetchResult:
        if not FIXTURE.exists():
            return DisclosureFetchResult(
                provider_name=self.name,
                source_class=self.source_class,
                status=DisclosureStatus.NOT_CONFIGURED,
                query_start=start_time.strftime("%Y-%m-%d"),
                query_end=end_time.strftime("%Y-%m-%d"),
                retrieval_time=datetime.now().isoformat(timespec="seconds"),
                row_count=0,
                errors=["fixture missing"],
            )
        rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if symbols:
            sym = set(symbols)
            rows = [r for r in rows if r.get("stock_code") in sym]
        st = DisclosureStatus.SUCCESS_WITH_ROWS if rows else DisclosureStatus.SUCCESS_ZERO_RESULTS
        return DisclosureFetchResult(
            provider_name=self.name,
            source_class=self.source_class,
            status=st,
            query_start=start_time.strftime("%Y-%m-%d"),
            query_end=end_time.strftime("%Y-%m-%d"),
            retrieval_time=datetime.now().isoformat(timespec="seconds"),
            row_count=len(rows),
            rows=rows,
            raw_artifact_paths=[str(FIXTURE.relative_to(ROOT))],
        )
