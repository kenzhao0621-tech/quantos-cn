"""Official disclosure ingestion, coverage, and readiness metadata."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
META_PATH = ROOT / "data" / "disclosures" / "disclosure_meta.json"
DISC_ROOT = ROOT / "data" / "disclosures"


def persist_disclosures(rows: list[dict[str, Any]], *, provider: str, run_id: str = "") -> dict[str, Any]:
    from quant.disclosures.raw_store import save_normalized_batch
    from quant.disclosures.warehouse_sync import sync_disclosures_to_warehouse

    DISC_ROOT.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    norm = save_normalized_batch(rows, date=date) if rows else ""
    wh = sync_disclosures_to_warehouse(rows, date=date) if rows else {"row_count": 0}
    meta = load_disclosure_meta()
    meta.update({
        "provider": provider,
        "run_id": run_id,
        "row_count": len(rows),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "normalized_path": norm,
        "warehouse": wh,
        "query_state": "DISCLOSURE_QUERY_COMPLETE_WITH_ROWS" if rows else meta.get("query_state", ""),
    })
    save_disclosure_meta(meta)
    path = DISC_ROOT / f"disclosures_{provider}.json"
    path.write_text(json.dumps({"provider": provider, "row_count": len(rows), "rows": rows[:2000]}, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path.relative_to(ROOT)), "row_count": len(rows), "provider": provider, **meta}


def load_disclosure_meta() -> dict[str, Any]:
    if META_PATH.exists():
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    return {
        "query_state": "DISCLOSURE_DATA_UNAVAILABLE",
        "primary_provider": "",
        "primary_status": "",
        "row_count": 0,
        "verified_zero_results": False,
    }


def save_disclosure_meta(meta: dict[str, Any]) -> None:
    META_PATH.parent.mkdir(parents=True, exist_ok=True)
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def disclosure_coverage_report() -> dict[str, Any]:
    meta = load_disclosure_meta()
    row_count = int(meta.get("row_count", 0) or 0)
    from quant.disclosures.candidate_gate import evaluate_disclosure_readiness
    readiness = evaluate_disclosure_readiness(meta)
    return {
        "file_count": len(list(DISC_ROOT.glob("*.json"))) if DISC_ROOT.exists() else 0,
        "total_rows": row_count,
        "status": "available" if readiness.passed else meta.get("query_state", "unavailable"),
        "query_state": meta.get("query_state", "DISCLOSURE_DATA_UNAVAILABLE"),
        "primary_provider": meta.get("primary_provider", ""),
        "primary_status": meta.get("primary_status", ""),
        "verified_zero_results": meta.get("verified_zero_results", False),
        "disclosure_readiness": readiness.to_dict(),
        "candidate_gate": readiness.passed,
    }


def run_official_disclosure_update(*, days_back: int = 30, use_network: bool = True) -> dict[str, Any]:
    from quant.disclosures.fetch_pipeline import fetch_official_disclosures

    result = fetch_official_disclosures(days_back=days_back, use_network=use_network)
    rows = result.get("rows", [])
    meta = {
        "query_state": result.get("query_state"),
        "primary_provider": result.get("primary_provider"),
        "primary_status": result.get("primary_status"),
        "row_count": result.get("row_count", 0),
        "verified_zero_results": result.get("verified_zero_results", False),
        "normalized_path": result.get("normalized_path", ""),
        "results": result.get("results", []),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_disclosure_meta(meta)
    if rows:
        persist_disclosures(rows, provider=result.get("primary_provider", "cninfo_official"))
    from quant.disclosures.candidate_gate import evaluate_disclosure_readiness
    rep = disclosure_coverage_report()
    rep["readiness"] = evaluate_disclosure_readiness(meta).to_dict()
    rep["fetch"] = {k: result[k] for k in ("query_state", "primary_status", "row_count", "verified_zero_results") if k in result}
    return rep
