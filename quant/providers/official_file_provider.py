"""Official file download / local authorized file ingestion."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from quant.freshness_contract import FreshnessClass
from quant.provider_result import ProviderResult, ProviderStatus
from quant.providers.adapter_mixin import default_capabilities, default_freshness_validate

ROOT = Path(__file__).resolve().parents[2]
IMPORTS_DIR = ROOT / "data" / "imports"


class OfficialFileDownloadProvider:
    name = "official_file"

    def configured(self) -> bool:
        return True

    def capabilities(self):
        return default_capabilities(
            self.name,
            datasets={"sector_membership": "HISTORICAL", "fundamentals": "HISTORICAL", "official_disclosures": "HISTORICAL"},
            warnings=("User-supplied official files only",),
        )

    def permission_probe(self) -> tuple[bool, str]:
        return True, "local file ingestion"

    def health_check(self, *, probe_live: bool = False):
        from quant.provider_base_v2 import ProviderHealth
        return ProviderHealth(
            provider_name=self.name, configured=True, reachable=True, authenticated=None,
            status="READY", latency_ms=None, capabilities=self.capabilities(),
            last_error_class=None, last_error_message=None, checked_at=datetime.now(),
        )

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        path = Path(kwargs.get("path", ""))
        if not path.exists():
            return ProviderResult(
                provider=self.name, dataset=dataset, status=ProviderStatus.FAILED,
                error=f"file not found: {path}", retrieved_at=datetime.now().isoformat(timespec="seconds"),
            )
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        suffix = path.suffix.lower()
        payload: dict[str, Any] = {
            "path": str(path), "sha256": sha, "size": len(raw),
            "source_dataset": path.name, "freshness_class": FreshnessClass.HISTORICAL.value,
        }
        if suffix == ".json":
            payload["content"] = json.loads(raw.decode("utf-8"))
        elif suffix == ".csv":
            import pandas as pd
            payload["rows"] = pd.read_csv(path).to_dict(orient="records")
            payload["row_count"] = len(payload["rows"])
        manifest = {
            "source_url": kwargs.get("source_url", f"file://{path}"),
            "retrieval_time": datetime.now().isoformat(timespec="seconds"),
            "file_hash": sha,
            "freshness_class": FreshnessClass.HISTORICAL.value,
            "authorization_note": kwargs.get("authorization_note", "user-owned file"),
        }
        payload["manifest"] = manifest
        return ProviderResult(
            provider=self.name, dataset=dataset, status=ProviderStatus.SUCCESS, payload=payload,
            retrieved_at=datetime.now().isoformat(timespec="seconds"),
            data_hash=sha[:16], row_count=payload.get("row_count", 0),
            freshness=FreshnessClass.HISTORICAL.value,
            endpoint="local_file", source_dataset=path.name, is_live=False,
        )

    def normalize(self, dataset: str, raw: Any) -> Any:
        return raw

    def quality_validate(self, dataset: str, payload: Any) -> tuple[bool, list[str]]:
        if isinstance(payload, dict) and (payload.get("rows") or payload.get("content")):
            return True, []
        return False, ["no parseable content"]

    def freshness_validate(self, dataset: str, result: ProviderResult, **kwargs: Any):
        return default_freshness_validate(dataset, result, sla_key="fundamentals", require_live=False)

    def persist(self, dataset: str, result: ProviderResult, *, run_id: str) -> Optional[dict[str, Any]]:
        if not result.ok or not isinstance(result.payload, dict):
            return None
        dest = IMPORTS_DIR / run_id / f"{dataset}.manifest.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result.payload.get("manifest", {}), indent=2), encoding="utf-8")
        return {"manifest_path": str(dest)}
