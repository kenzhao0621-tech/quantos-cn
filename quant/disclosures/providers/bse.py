"""BSE official disclosure provider."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from quant.disclosures.providers.cninfo import CNInfoOfficialProvider
from quant.disclosures.protocol import DisclosureFetchResult, DisclosureProviderHealth, DisclosureCapabilities


class BSEDisclosureProvider:
    name = "bse_official"
    source_class = "BSE_LISTED_ANNOUNCEMENTS"

    def __init__(self) -> None:
        self._cninfo = CNInfoOfficialProvider()

    def health_check(self) -> DisclosureProviderHealth:
        h = self._cninfo.health_check()
        h.provider_name = self.name
        return h

    def capabilities(self) -> DisclosureCapabilities:
        c = self._cninfo.capabilities()
        c.provider_name = self.name
        c.exchanges = ["BSE"]
        return c

    def fetch_announcements(
        self,
        start_time: datetime,
        end_time: datetime,
        symbols: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
    ) -> DisclosureFetchResult:
        result = self._cninfo.fetch_announcements(start_time, end_time, symbols, categories)
        result.provider_name = self.name
        result.source_class = self.source_class
        result.rows = [r for r in result.rows if r.get("exchange") == "BSE"]
        result.row_count = len(result.rows)
        return result
