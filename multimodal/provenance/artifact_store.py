"""SHA-256 provenance and artifact persistence."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

ArtifactKind = Literal["images", "documents"]


class ArtifactStore:
    """Persist artifacts under artifacts/images/ and artifacts/documents/."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = (root or Path.cwd() / "artifacts").resolve()
        self.images_root = self.root / "images"
        self.documents_root = self.root / "documents"
        for sub in (
            self.images_root / "generated",
            self.images_root / "edited",
            self.images_root / "manifests",
            self.documents_root / "originals",
            self.documents_root / "rendered_pages",
            self.documents_root / "manifests",
        ):
            sub.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _subdir(self, kind: ArtifactKind, category: str) -> Path:
        base = self.images_root if kind == "images" else self.documents_root
        path = base / category
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_bytes(
        self,
        data: bytes,
        *,
        kind: ArtifactKind,
        category: str,
        suffix: str,
        source_path: Optional[Path] = None,
        request_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        digest = self.sha256_bytes(data)
        short = digest[:16]
        out_dir = self._subdir(kind, category)
        out_path = out_dir / f"{short}{suffix}"
        if not out_path.exists():
            out_path.write_bytes(data)

        manifest = {
            "artifact_id": str(uuid4()),
            "request_id": request_id,
            "kind": kind,
            "category": category,
            "path": str(out_path),
            "sha256": digest,
            "size_bytes": len(data),
            "source_path": str(source_path) if source_path else None,
            "source_sha256": self.sha256_file(source_path) if source_path and source_path.exists() else None,
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            **(extra or {}),
        }
        manifest_path = self._subdir(kind, "manifests") / f"{short}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        manifest["manifest_path"] = str(manifest_path)
        return manifest

    def save_file_copy(
        self,
        src: Path,
        *,
        kind: ArtifactKind,
        category: str,
        request_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        data = src.read_bytes()
        digest = self.sha256_bytes(data)
        short = digest[:16]
        out_dir = self._subdir(kind, category)
        out_path = out_dir / f"{short}{src.suffix}"
        if not out_path.exists():
            shutil.copy2(src, out_path)
        return self.save_bytes(
            out_path.read_bytes(),
            kind=kind,
            category=category,
            suffix=src.suffix,
            source_path=src,
            request_id=request_id,
            extra=extra,
        )
