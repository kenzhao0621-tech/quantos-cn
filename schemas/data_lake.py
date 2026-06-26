"""Atomic snapshot persistence under data/."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data"


@dataclass
class SnapshotManifest:
    dataset: str
    trade_date: str
    saved_at: str
    raw_path: str
    normalized_path: str
    provider: str
    data_hash: str
    row_count: int = 0
    schema_version: str = "2026-06-16-v4"
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


def save_snapshot(
    dataset: str,
    *,
    raw_payload: Any,
    normalized_payload: Any,
    provider: str,
    trade_date: Optional[str] = None,
    data_root: Path = DATA_ROOT,
) -> SnapshotManifest:
    """Write raw + normalized JSON and manifest atomically."""
    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    saved_at = datetime.now().isoformat(timespec="seconds")
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    raw_dir = data_root / "raw" / trade_date / dataset / provider
    norm_dir = data_root / "normalized" / trade_date / dataset
    manifest_dir = data_root / "manifests" / trade_date

    raw_path = raw_dir / f"{stamp}.json"
    norm_path = norm_dir / "latest.json"
    manifest_path = manifest_dir / f"{dataset}.manifest.json"

    raw_doc = {
        "saved_at": saved_at,
        "provider": provider,
        "dataset": dataset,
        "trade_date": trade_date,
        "payload": raw_payload,
    }
    norm_doc = {
        "saved_at": saved_at,
        "provider": provider,
        "dataset": dataset,
        "trade_date": trade_date,
        "payload": normalized_payload,
    }

    raw_text = json.dumps(raw_doc, ensure_ascii=False, indent=2, default=str)
    norm_text = json.dumps(norm_doc, ensure_ascii=False, indent=2, default=str)
    data_hash = _sha256_bytes(norm_text.encode("utf-8"))

    row_count = 0
    if isinstance(normalized_payload, dict) and "rows" in normalized_payload:
        row_count = len(normalized_payload["rows"])
    elif isinstance(normalized_payload, list):
        row_count = len(normalized_payload)

    _atomic_write(raw_path, raw_text)
    _atomic_write(norm_path, norm_text)

    manifest = SnapshotManifest(
        dataset=dataset,
        trade_date=trade_date,
        saved_at=saved_at,
        raw_path=str(raw_path.relative_to(data_root)),
        normalized_path=str(norm_path.relative_to(data_root)),
        provider=provider,
        data_hash=data_hash,
        row_count=row_count,
    )
    _atomic_write(manifest_path, json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
    return manifest


def load_latest_normalized(
    dataset: str,
    *,
    trade_date: Optional[str] = None,
    data_root: Path = DATA_ROOT,
) -> Optional[dict[str, Any]]:
    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    path = data_root / "normalized" / trade_date / dataset / "latest.json"
    if not path.exists():
        # fallback: most recent date folder
        base = data_root / "normalized"
        if not base.exists():
            return None
        dates = sorted((p.name for p in base.iterdir() if p.is_dir()), reverse=True)
        for d in dates:
            candidate = base / d / dataset / "latest.json"
            if candidate.exists():
                path = candidate
                break
        else:
            return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc
