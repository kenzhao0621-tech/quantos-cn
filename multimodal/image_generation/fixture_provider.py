"""Deterministic fixture image generation with PIL."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from multimodal.contracts.types import ImageArtifact, ImageGenerationRequest, utc_now_iso
from multimodal.provenance.artifact_store import ArtifactStore

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    Image = None  # type: ignore


class FixtureImageProvider:
    name = "fixture"
    model = "deterministic-pil-v1"

    def __init__(self, store: ArtifactStore | None = None) -> None:
        self.store = store or ArtifactStore()

    def health_check(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "status": "ok" if Image else "missing_pillow",
            "capabilities": ["text-to-image", "deterministic"],
        }

    def capabilities(self) -> list[str]:
        return ["text-to-image", "deterministic", "transparent_background"]

    def _seed_from_request(self, request: ImageGenerationRequest) -> int:
        if request.seed is not None:
            return request.seed
        h = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()
        return int(h[:8], 16)

    def generate(self, request: ImageGenerationRequest) -> ImageArtifact:
        if Image is None:
            raise RuntimeError("Pillow is required for fixture image generation")

        t0 = time.perf_counter()
        seed = self._seed_from_request(request)
        mode = "RGBA" if request.transparent_background else "RGB"
        img = Image.new(mode, (request.width, request.height))
        draw = ImageDraw.Draw(img)

        # Deterministic gradient from seed
        r = (seed >> 16) & 0xFF
        g = (seed >> 8) & 0xFF
        b = seed & 0xFF
        for y in range(request.height):
            for x in range(0, request.width, max(1, request.width // 64)):
                factor = (x + y) / max(1, request.width + request.height)
                color = (
                    int(r * (0.3 + 0.7 * factor)) % 256,
                    int(g * (0.3 + 0.7 * (1 - factor))) % 256,
                    int(b * (0.5 + 0.5 * factor)) % 256,
                    255 if mode == "RGBA" else None,
                )
                if mode == "RGB":
                    draw.point((x, y), fill=color[:3])
                else:
                    draw.point((x, y), fill=color)  # type: ignore[arg-type]

        label = request.prompt[:40] if request.prompt else f"seed={seed}"
        draw.rectangle([10, 10, min(request.width - 10, 300), 50], fill=(0, 0, 0, 180) if mode == "RGBA" else (0, 0, 0))
        draw.text((20, 20), label, fill=(255, 255, 255))

        import io

        buf = io.BytesIO()
        img.save(buf, format=request.output_format or "PNG")
        data = buf.getvalue()

        saved = self.store.save_bytes(
            data,
            kind="images",
            category="generated",
            suffix=".png",
            request_id=request.request_id,
            extra={"provider": self.name, "seed": seed, "prompt": request.prompt},
        )

        runtime_ms = (time.perf_counter() - t0) * 1000
        return ImageArtifact(
            path=saved["path"],
            sha256=saved["sha256"],
            width=request.width,
            height=request.height,
            format=request.output_format or "PNG",
            provider=self.name,
            model=self.model,
            request_id=request.request_id,
            timestamp=utc_now_iso(),
            source_path=request.source_image_path,
            source_sha256=request.source_sha256,
            runtime_ms=runtime_ms,
            cost_estimate_usd=0.0,
            confidence=1.0,
            license_notes="fixture-generated",
            manifest_path=saved.get("manifest_path"),
        )
