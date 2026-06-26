"""Manual CSV/JSON snapshot import with SHA-256 integrity."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from quant.provider_result import ProviderResult, ProviderStatus


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    code = str(row.get("code") or row.get("代码") or "").zfill(6)
    name = str(row.get("name") or row.get("名称") or "")
    price = row.get("price") or row.get("最新价") or row.get("close") or 0
    chg = row.get("change_pct") or row.get("涨跌幅") or 0
    return {
        "code": code,
        "name": name,
        "price": float(price) if price not in ("", None) else 0.0,
        "change_pct": float(chg) if chg not in ("", None) else 0.0,
        **{k: v for k, v in row.items() if k not in ("code", "name", "price", "change_pct")},
    }


class ManualSnapshotProvider:
    name = "manual_snapshot"

    def __init__(self, import_dir: Optional[Path] = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.import_dir = import_dir or (root / "data" / "imports")

    def load_file(self, path: Path, *, dataset: str = "spot_quotes") -> ProviderResult:
        if not path.exists():
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.FAILED,
                error=f"file not found: {path}",
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        file_hash = _sha256_file(path)
        suffix = path.suffix.lower()
        try:
            if suffix == ".json":
                doc = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(doc, list):
                    payload = {"rows": [_normalize_row(r) for r in doc]}
                elif isinstance(doc, dict) and "rows" in doc:
                    payload = {"rows": [_normalize_row(r) for r in doc["rows"]], **{k: v for k, v in doc.items() if k != "rows"}}
                else:
                    payload = doc
            elif suffix == ".csv":
                rows = [_normalize_row(r) for r in _parse_csv(path)]
                payload = {"rows": rows, "source_file": str(path.name)}
            else:
                return ProviderResult(
                    provider=self.name,
                    dataset=dataset,
                    status=ProviderStatus.FAILED,
                    error=f"unsupported format: {suffix}",
                    retrieved_at=datetime.now().isoformat(timespec="seconds"),
                )
            row_count = len(payload.get("rows", [])) if isinstance(payload, dict) else 0
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.SUCCESS if row_count or dataset != "spot_quotes" else ProviderStatus.EMPTY,
                payload=payload,
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
                data_hash=file_hash[:16],
                row_count=row_count,
                freshness="MANUAL_IMPORT",
                limitations=(f"Manual import SHA-256={file_hash[:16]}",),
            )
        except Exception as e:
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.FAILED,
                error=str(e),
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        path = kwargs.get("path")
        if path:
            return self.load_file(Path(path), dataset=dataset)
        # Auto-pick latest import for dataset
        if not self.import_dir.exists():
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.NOT_CONFIGURED,
                error=f"no import directory: {self.import_dir}",
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        candidates = sorted(
            list(self.import_dir.glob(f"{dataset}.*"))
            + list(self.import_dir.glob("*.csv"))
            + list(self.import_dir.glob("*.json")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return ProviderResult(
                provider=self.name,
                dataset=dataset,
                status=ProviderStatus.NOT_CONFIGURED,
                error="no manual import files found",
                retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        return self.load_file(candidates[0], dataset=dataset)
