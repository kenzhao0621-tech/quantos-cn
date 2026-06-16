"""Pillow-based image editing operations."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional, Tuple

from multimodal.provenance.artifact_store import ArtifactStore

try:
    from PIL import Image, ImageFilter
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageFilter = None  # type: ignore


def _require_pillow() -> None:
    if Image is None:
        raise RuntimeError("Pillow is required for image editing")


def load_image(path: Path) -> "Image.Image":
    _require_pillow()
    return Image.open(path)


def crop(
    path: Path,
    box: Tuple[int, int, int, int],
    *,
    store: Optional[ArtifactStore] = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    _require_pillow()
    img = load_image(path)
    cropped = img.crop(box)
    return _save_image(cropped, store, request_id, category="edited", op="crop")


def resize(
    path: Path,
    size: Tuple[int, int],
    *,
    store: Optional[ArtifactStore] = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    _require_pillow()
    img = load_image(path)
    resized = img.resize(size, Image.Resampling.LANCZOS)
    return _save_image(resized, store, request_id, category="edited", op="resize")


def remove_background_simple(
    path: Path,
    *,
    threshold: int = 240,
    store: Optional[ArtifactStore] = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    """Simple near-white background removal to RGBA."""
    _require_pillow()
    img = load_image(path).convert("RGBA")
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r >= threshold and g >= threshold and b >= threshold:
                pixels[x, y] = (r, g, b, 0)
    return _save_image(img, store, request_id, category="edited", op="background_removal")


def upscale(
    path: Path,
    scale: float = 2.0,
    *,
    store: Optional[ArtifactStore] = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    _require_pillow()
    img = load_image(path)
    new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    up = img.resize(new_size, Image.Resampling.LANCZOS)
    if ImageFilter:
        up = up.filter(ImageFilter.SHARPEN)
    return _save_image(up, store, request_id, category="edited", op="upscale")


def _save_image(
    img: "Image.Image",
    store: Optional[ArtifactStore],
    request_id: Optional[str],
    *,
    category: str,
    op: str,
) -> dict[str, Any]:
    buf = io.BytesIO()
    fmt = "PNG" if img.mode == "RGBA" else "PNG"
    img.save(buf, format=fmt)
    data = buf.getvalue()
    artifact_store = store or ArtifactStore()
    saved = artifact_store.save_bytes(
        data,
        kind="images",
        category=category,
        suffix=".png",
        request_id=request_id,
        extra={"operation": op, "width": img.width, "height": img.height},
    )
    saved["width"] = img.width
    saved["height"] = img.height
    saved["format"] = fmt
    saved["has_alpha"] = img.mode == "RGBA"
    return saved
