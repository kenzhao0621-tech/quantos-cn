"""Real-data acceptance pipeline — end-to-end V4 validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quant import PAPER_TRADING_ONLY, REAL_MONEY_EXECUTION_DISABLED
from quant.composite_provider import CompositeMarketDataProvider
from quant.data_lake import save_snapshot
from quant.run_context import new_run_id
from quant.data_quality import run_snapshot_quality_checks


def run_real_data_acceptance(
    *,
    datasets: list[str] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """
    Attempt full V4 data pipeline:
    fetch → quality check → optional lake persist.
    """
    if not PAPER_TRADING_ONLY or not REAL_MONEY_EXECUTION_DISABLED:
        return {
            "accepted": False,
            "error": "safety gates not enforced",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }

    datasets = datasets or ["indices", "spot_quotes", "trading_calendar"]
    composite = CompositeMarketDataProvider()
    if "manual_snapshot" in composite.registry:
        del composite.registry["manual_snapshot"]
    run_id = new_run_id()
    fetch_results = composite.fetch_market_snapshot(
        datasets=datasets,
        route_mode="latest_available",
        live_only=True,
    )

    quality_results = []
    persisted = []
    all_ok = True

    for ds, composite_result in fetch_results.items():
        if not composite_result.ok or composite_result.result is None:
            all_ok = False
            quality_results.append(
                run_snapshot_quality_checks(ds, None, min_rows=1).to_dict()
            )
            continue
        winner = composite_result.result
        qr = run_snapshot_quality_checks(ds, winner.payload, data_hash=winner.data_hash)
        quality_results.append(qr.to_dict())
        if not qr.passed:
            all_ok = False
        if persist and qr.passed:
            manifest = save_snapshot(
                ds,
                run_id=run_id,
                raw_payload=winner.payload,
                normalized_payload=winner.payload,
                provider=winner.provider,
                provenance={
                    "endpoint": winner.endpoint,
                    "source_dataset": winner.source_dataset,
                    "freshness": winner.freshness,
                    "is_live": winner.is_live,
                    "is_end_of_day": winner.is_end_of_day,
                    "market_date": winner.market_date,
                },
            )
            persisted.append(manifest.to_dict())

    return {
        "accepted": all_ok,
        "run_id": run_id,
        "paper_trading_only": PAPER_TRADING_ONLY,
        "real_money_execution_disabled": REAL_MONEY_EXECUTION_DISABLED,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "fetch": {k: v.to_dict() for k, v in fetch_results.items()},
        "quality": {"datasets": quality_results, "passed": all_ok},
        "persisted": persisted,
    }
