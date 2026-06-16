"""Async job base with run_id, checkpoint, and artifact manifest."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.config import ROOT


@dataclass
class JobManifest:
    run_id: str
    job_type: str
    status: str = "QUEUED"
    retry_budget: int = 3
    retries_used: int = 0
    checkpoint: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkerJob:
    def __init__(self, job_type: str, run_id: str | None = None, manifest_dir: Path | None = None) -> None:
        self.manifest = JobManifest(run_id=run_id or str(uuid.uuid4()), job_type=job_type)
        self.manifest_dir = manifest_dir or ROOT / "data" / "gateway" / "jobs"
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        self.manifest.status = "RUNNING"
        self.manifest.started_at = datetime.now(timezone.utc).isoformat()
        self._persist()

    def checkpoint(self, data: dict[str, Any]) -> None:
        self.manifest.checkpoint.update(data)
        self._persist()

    def complete(self, artifacts: list[str] | None = None) -> None:
        self.manifest.status = "COMPLETED"
        self.manifest.finished_at = datetime.now(timezone.utc).isoformat()
        if artifacts:
            self.manifest.artifacts.extend(artifacts)
        self._persist()

    def fail(self, error: str) -> None:
        self.manifest.retries_used += 1
        if self.manifest.retries_used >= self.manifest.retry_budget:
            self.manifest.status = "FAILED"
        else:
            self.manifest.status = "RETRY"
        self.manifest.error = error
        self.manifest.finished_at = datetime.now(timezone.utc).isoformat()
        self._persist()

    def _persist(self) -> None:
        path = self.manifest_dir / f"{self.manifest.run_id}.json"
        path.write_text(json.dumps(self.manifest.to_dict(), indent=2), encoding="utf-8")
