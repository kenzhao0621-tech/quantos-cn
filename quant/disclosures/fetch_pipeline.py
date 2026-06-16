"""Disclosure fetch orchestration across official providers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from quant.disclosures.providers import (
    BSEDisclosureProvider,
    CNInfoOfficialProvider,
    LocalDisclosureSnapshotProvider,
    SSEDisclosureProvider,
    SZSEDisclosureProvider,
)
from quant.disclosures.protocol import DisclosureFetchResult, DisclosureStatus
from quant.disclosures.raw_store import save_normalized_batch


def get_providers(*, include_local: bool = False) -> list[Any]:
    providers = [
        CNInfoOfficialProvider(),
        SSEDisclosureProvider(),
        SZSEDisclosureProvider(),
        BSEDisclosureProvider(),
    ]
    if include_local:
        providers.append(LocalDisclosureSnapshotProvider())
    return providers


def fetch_official_disclosures(
    *,
    days_back: int = 30,
    symbols: Optional[list[str]] = None,
    use_network: bool = True,
) -> dict[str, Any]:
    end = datetime.now()
    start = end - timedelta(days=days_back)
    results: list[DisclosureFetchResult] = []
    all_rows: list[dict[str, Any]] = []
    primary: Optional[DisclosureFetchResult] = None

    if use_network:
        cninfo = CNInfoOfficialProvider()
        primary = cninfo.fetch_announcements(start, end, symbols)
        results.append(primary)
        if primary.query_completed:
            all_rows.extend(primary.rows)
        else:
            for p in [SSEDisclosureProvider(), SZSEDisclosureProvider(), BSEDisclosureProvider()]:
                r = p.fetch_announcements(start, end, symbols)
                results.append(r)
                if r.query_completed and r.row_count > 0:
                    all_rows.extend(r.rows)
                    primary = r
                    break

    norm_path = ""
    if all_rows:
        norm_path = save_normalized_batch(all_rows, date=end.strftime("%Y-%m-%d"))

    query_state = "DISCLOSURE_DATA_UNAVAILABLE"
    if primary and primary.query_completed:
        query_state = "DISCLOSURE_QUERY_COMPLETE_ZERO_RESULTS" if primary.row_count == 0 else "DISCLOSURE_QUERY_COMPLETE_WITH_ROWS"

    return {
        "query_state": query_state,
        "primary_provider": primary.provider_name if primary else "",
        "primary_status": primary.status.value if primary else "NOT_CONFIGURED",
        "row_count": len(all_rows),
        "verified_zero_results": primary is not None and primary.status == DisclosureStatus.SUCCESS_ZERO_RESULTS,
        "normalized_path": norm_path,
        "results": [r.to_dict() for r in results],
        "rows": all_rows[:5000],
    }
