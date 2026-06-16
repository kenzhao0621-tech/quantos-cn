"""Fixture image analyzer with region bounding boxes."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from multimodal.contracts.types import VisualAnalysisResult, utc_now_iso
from multimodal.provenance.artifact_store import ArtifactStore

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore


class FixtureImageAnalyzer:
    name = "fixture_analyzer"
    model = "heuristic-v1"

    def __init__(self, store: ArtifactStore | None = None) -> None:
        self.store = store or ArtifactStore()

    def health_check(self) -> dict[str, Any]:
        return {"provider": self.name, "status": "ok" if Image else "missing_pillow"}

    def analyze_image(self, image_path: Path, *, request_id: str | None = None) -> VisualAnalysisResult:
        if Image is None:
            raise RuntimeError("Pillow is required for image analysis")

        t0 = time.perf_counter()
        path = Path(image_path).resolve()
        sha = ArtifactStore.sha256_file(path)
        img = Image.open(path)
        w, h = img.size

        # Heuristic regions: quadrants + center label band
        regions = [
            {
                "id": "top_left",
                "bbox": [0, 0, w // 2, h // 2],
                "label": "quadrant_tl",
                "confidence": 0.9,
                "evidence_type": "geometry",
            },
            {
                "id": "top_right",
                "bbox": [w // 2, 0, w, h // 2],
                "label": "quadrant_tr",
                "confidence": 0.9,
                "evidence_type": "geometry",
            },
            {
                "id": "bottom_left",
                "bbox": [0, h // 2, w // 2, h],
                "label": "quadrant_bl",
                "confidence": 0.9,
                "evidence_type": "geometry",
            },
            {
                "id": "bottom_right",
                "bbox": [w // 2, h // 2, w, h],
                "label": "quadrant_br",
                "confidence": 0.9,
                "evidence_type": "geometry",
            },
            {
                "id": "caption_band",
                "bbox": [10, 10, min(300, w - 10), min(50, h - 10)],
                "label": "possible_text_band",
                "confidence": 0.7,
                "evidence_type": "heuristic",
            },
        ]

        mode = img.mode
        description = f"Fixture analysis of {path.name}: {w}x{h} {mode} image with {len(regions)} regions."
        runtime_ms = (time.perf_counter() - t0) * 1000

        return VisualAnalysisResult(
            image_path=str(path),
            source_sha256=sha,
            provider=self.name,
            request_id=request_id or "fixture",
            timestamp=utc_now_iso(),
            description=description,
            regions=regions,
            text_blocks=[{"bbox": regions[-1]["bbox"], "text": "[fixture OCR placeholder]", "confidence": 0.5}],
            confidence=0.85,
            warnings=[],
            runtime_ms=runtime_ms,
            evidence_type="fixture_analysis",
        )

    def compare_images(self, left: Path, right: Path, *, request_id: str | None = None) -> dict[str, Any]:
        if Image is None:
            raise RuntimeError("Pillow is required")
        l_img = Image.open(left)
        r_img = Image.open(right)
        same_size = l_img.size == r_img.size
        return {
            "request_id": request_id,
            "left": str(left),
            "right": str(right),
            "left_sha256": ArtifactStore.sha256_file(left),
            "right_sha256": ArtifactStore.sha256_file(right),
            "same_dimensions": same_size,
            "left_size": l_img.size,
            "right_size": r_img.size,
            "similarity_score": 1.0 if ArtifactStore.sha256_file(left) == ArtifactStore.sha256_file(right) else 0.5,
            "provider": self.name,
        }
