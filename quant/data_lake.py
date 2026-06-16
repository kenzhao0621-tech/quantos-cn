"""Atomic snapshot persistence under data/ with run_id binding."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data"


@dataclass
class SnapshotManifest:
    run_id: str
    dataset: str
    trade_date: str
    saved_at: str
    raw_path: str
    normalized_path: str
    provider: str
    data_hash: str
    row_count: int = 0
    schema_version: str = "akshare_sina_spot_v1"
    endpoint: str = ""
    source_dataset: str = ""
    freshness: str = ""
    is_live: bool = False
    is_end_of_day: bool = False
    is_manual: bool = False
    is_fixture: bool = False
    market_date: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def save_snapshot(
    dataset: str,
    *,
    run_id: str,
    raw_payload: Any,
    normalized_payload: Any,
    provider: str,
    trade_date: Optional[str] = None,
    data_root: Path = DATA_ROOT,
    provenance: Optional[dict[str, Any]] = None,
) -> SnapshotManifest:
    """Write raw + normalized JSON and run-bound manifest atomically."""
    prov = provenance or {}
    if isinstance(normalized_payload, dict):
        trade_date = trade_date or normalized_payload.get("market_date") or datetime.now().strftime("%Y-%m-%d")
    else:
        trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    saved_at = datetime.now().isoformat(timespec="seconds")
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    raw_dir = data_root / "raw" / provider / dataset / trade_date.replace("-", "/") / run_id
    norm_dir = data_root / "normalized" / dataset / trade_date.replace("-", "/") / run_id
    manifest_dir = data_root / "manifests" / run_id

    raw_path = raw_dir / f"{stamp}.json"
    norm_path = norm_dir / "normalized.json"
    manifest_path = manifest_dir / f"{dataset}.manifest.json"
    latest_pointer = data_root / "normalized" / dataset / "latest_run.json"

    raw_doc = {"run_id": run_id, "saved_at": saved_at, "provider": provider, "dataset": dataset,
               "trade_date": trade_date, "payload": raw_payload}
    norm_doc = {
        "run_id": run_id, "saved_at": saved_at, "provider": provider, "dataset": dataset,
        "trade_date": trade_date, "payload": normalized_payload,
        "endpoint": prov.get("endpoint", normalized_payload.get("endpoint", "") if isinstance(normalized_payload, dict) else ""),
        "source_dataset": prov.get("source_dataset", normalized_payload.get("source_dataset", "") if isinstance(normalized_payload, dict) else ""),
        "freshness": prov.get("freshness", normalized_payload.get("freshness", "") if isinstance(normalized_payload, dict) else ""),
        "is_live": prov.get("is_live", normalized_payload.get("is_live", False) if isinstance(normalized_payload, dict) else False),
        "is_end_of_day": prov.get("is_end_of_day", normalized_payload.get("is_end_of_day", False) if isinstance(normalized_payload, dict) else False),
        "is_manual": prov.get("is_manual", provider == "manual_snapshot"),
        "is_fixture": prov.get("is_fixture", False),
        "market_date": prov.get("market_date", normalized_payload.get("market_date", "") if isinstance(normalized_payload, dict) else ""),
    }

    raw_text = json.dumps(raw_doc, ensure_ascii=False, indent=2, default=str)
    norm_text = json.dumps(norm_doc, ensure_ascii=False, indent=2, default=str)
    data_hash = _sha256_bytes(norm_text.encode("utf-8"))

    row_count = 0
    if isinstance(normalized_payload, dict) and "rows" in normalized_payload:
        row_count = len(normalized_payload["rows"])

    _atomic_write(raw_path, raw_text)
    _atomic_write(norm_path, norm_text)
    _atomic_write(latest_pointer, json.dumps({
        "run_id": run_id, "dataset": dataset, "trade_date": trade_date,
        "normalized_path": str(norm_path.relative_to(data_root)),
        "provider": provider, "saved_at": saved_at,
    }, indent=2))

    manifest = SnapshotManifest(
        run_id=run_id, dataset=dataset, trade_date=trade_date, saved_at=saved_at,
        raw_path=str(raw_path.relative_to(data_root)),
        normalized_path=str(norm_path.relative_to(data_root)),
        provider=provider, data_hash=data_hash, row_count=row_count,
        endpoint=norm_doc.get("endpoint", ""),
        source_dataset=norm_doc.get("source_dataset", ""),
        freshness=norm_doc.get("freshness", ""),
        is_live=bool(norm_doc.get("is_live")),
        is_end_of_day=bool(norm_doc.get("is_end_of_day")),
        is_manual=bool(norm_doc.get("is_manual")),
        is_fixture=bool(norm_doc.get("is_fixture")),
        market_date=norm_doc.get("market_date", ""),
        extra={"code_commit": _git_commit()},
    )
    _atomic_write(manifest_path, json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
    return manifest


def load_by_run_id(dataset: str, run_id: str, *, data_root: Path = DATA_ROOT) -> Optional[dict[str, Any]]:
    manifest_path = data_root / "manifests" / run_id / f"{dataset}.manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    norm_path = data_root / manifest["normalized_path"]
    if not norm_path.exists():
        return None
    return json.loads(norm_path.read_text(encoding="utf-8"))


def load_latest_normalized(
    dataset: str,
    *,
    trade_date: Optional[str] = None,
    run_id: Optional[str] = None,
    data_root: Path = DATA_ROOT,
) -> Optional[dict[str, Any]]:
    if run_id:
        return load_by_run_id(dataset, run_id, data_root=data_root)
    pointer = data_root / "normalized" / dataset / "latest_run.json"
    if pointer.exists():
        meta = json.loads(pointer.read_text(encoding="utf-8"))
        path = data_root / meta["normalized_path"]
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    path = data_root / "normalized" / trade_date / dataset / "latest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None
