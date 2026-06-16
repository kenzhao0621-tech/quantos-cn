"""Run daily analysis from a persisted quant run_id snapshot."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from quant.data_lake import DATA_ROOT, load_by_run_id
from tools.china_quant.daily_runner import DailyRunResult, _run_with_live_data
from tools.china_quant.modes import OperatingMode
from tools.china_quant.providers.base import DataEnvelope, DataFreshness


def _doc_to_envelope(doc: dict[str, Any], *, source_id: str) -> DataEnvelope:
    payload = doc.get("payload", doc)
    freshness_raw = doc.get("freshness", payload.get("freshness", "PARTIAL_DATA") if isinstance(payload, dict) else "PARTIAL_DATA")
    try:
        freshness = DataFreshness(freshness_raw)
    except ValueError:
        freshness = DataFreshness.PARTIAL_DATA
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    market_date = doc.get("market_date") or payload.get("market_date", "") if isinstance(payload, dict) else ""
    ts = datetime.now()
    if market_date:
        try:
            ts = datetime.fromisoformat(market_date)
        except ValueError:
            pass
    return DataEnvelope(
        provider=doc.get("provider", "quant_lake"),
        payload=payload,
        retrieval_timestamp=datetime.fromisoformat(doc["saved_at"]) if doc.get("saved_at") else datetime.now(),
        market_timestamp=ts,
        freshness=freshness,
        source_id=source_id,
        limitations=[f"run_id={doc.get('run_id', '')}"],
        row_count=len(rows),
    )


def run_from_run_id(
    run_id: str,
    fixtures_dir: Path,
    *,
    datasets: Optional[list[str]] = None,
) -> DailyRunResult:
    """Consume persisted snapshots for run_id — no silent refetch."""
    mode = OperatingMode.LATEST_AVAILABLE
    spot_doc = load_by_run_id("spot_quotes", run_id)
    if not spot_doc:
        raise ValueError(f"spot_quotes missing for run_id={run_id}")

    indices_doc = load_by_run_id("indices", run_id) or {
        "payload": {"sh": {"close": 0, "name": "上证指数", "source": "missing"}},
        "provider": "none",
        "freshness": "DATA_UNAVAILABLE",
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": run_id,
    }
    boards_doc = load_by_run_id("sector_boards", run_id) or {
        "payload": {"rows": []},
        "provider": "none",
        "freshness": "DATA_UNAVAILABLE",
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": run_id,
    }

    spot_env = _doc_to_envelope(spot_doc, source_id=f"run:{run_id}:spot")
    indices_env = _doc_to_envelope(indices_doc, source_id=f"run:{run_id}:indices")
    boards_env = _doc_to_envelope(boards_doc, source_id=f"run:{run_id}:boards")

    analysis_date = (
        spot_doc.get("market_date")
        or spot_doc.get("payload", {}).get("market_date")
        or datetime.now().strftime("%Y-%m-%d")
    )
    limitations = [
        f"input_run_id={run_id}",
        f"spot_provider={spot_doc.get('provider', '')}",
        f"freshness={spot_doc.get('freshness', '')}",
    ]
    if indices_doc.get("provider") == "none":
        limitations.append("indices unavailable — breadth fallback may apply")
    provider_status = {
        "run_id": run_id,
        "spot": spot_doc.get("provider"),
        "indices": indices_doc.get("provider"),
        "sectors": boards_doc.get("provider"),
        "spot_rows": spot_env.row_count,
        "data_root": str(DATA_ROOT),
    }
    return _run_with_live_data(
        mode,
        analysis_date,
        indices_env,
        spot_env,
        boards_env,
        200,
        3,
        limitations,
        provider_status,
        fixtures_dir,
    )
