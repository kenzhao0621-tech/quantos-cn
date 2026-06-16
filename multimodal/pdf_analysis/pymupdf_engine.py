"""PyMuPDF PDF engine with fixture fallback."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Optional

from multimodal.contracts.types import DocumentArtifact, PdfParseRequest, utc_now_iso
from multimodal.pdf_analysis.triage import triage_pdf
from multimodal.provenance.artifact_store import ArtifactStore

_PYMUPDF_AVAILABLE = False
try:
    import fitz  # noqa: F401

    _PYMUPDF_AVAILABLE = True
except ImportError:
    pass


class PyMuPDFEngine:
    name = "pymupdf" if _PYMUPDF_AVAILABLE else "fixture_pdf"
    model = "pymupdf" if _PYMUPDF_AVAILABLE else "minimal-bytes-v1"

    def __init__(self, store: ArtifactStore | None = None) -> None:
        self.store = store or ArtifactStore()

    def health_check(self) -> dict[str, Any]:
        return {
            "engine": self.name,
            "pymupdf_available": _PYMUPDF_AVAILABLE,
            "status": "ok",
        }

    def parse_pdf(self, request: PdfParseRequest) -> DocumentArtifact:
        path = Path(request.input_path).resolve()
        if not path.exists():
            raise FileNotFoundError(str(path))

        t0 = time.perf_counter()
        source_sha = ArtifactStore.sha256_file(path)
        self.store.save_file_copy(path, kind="documents", category="originals", request_id=request.request_id)

        triage = triage_pdf(path, output_dir=path.parent)
        pages: list[dict[str, Any]] = []
        rendered: list[str] = []
        text_parts: list[str] = []
        warnings: list[str] = []

        if _PYMUPDF_AVAILABLE:
            pages, rendered, text_parts, warnings = self._parse_with_pymupdf(path, request)
        else:
            pages, rendered, text_parts, warnings = self._parse_fixture(path, request)

        runtime_ms = (time.perf_counter() - t0) * 1000
        return DocumentArtifact(
            document_id=str(uuid.uuid4()),
            source_path=str(path),
            source_sha256=source_sha,
            page_count=len(pages) or triage.get("page_count", 1),
            provider=self.name,
            request_id=request.request_id,
            timestamp=utc_now_iso(),
            pages=pages,
            text_extracted="\n\n".join(text_parts),
            triage_json_path=triage.get("triage_json_path"),
            triage_md_path=triage.get("triage_md_path"),
            rendered_page_paths=rendered,
            runtime_ms=runtime_ms,
            confidence=0.95 if _PYMUPDF_AVAILABLE else 0.6,
            warnings=warnings,
        )

    def _parse_with_pymupdf(self, path: Path, request: PdfParseRequest) -> tuple[list, list, list, list]:
        import fitz

        pages_out: list[dict[str, Any]] = []
        rendered: list[str] = []
        text_parts: list[str] = []
        warnings: list[str] = []

        doc = fitz.open(path)
        page_indices = request.pages if request.pages is not None else list(range(doc.page_count))
        zoom = request.render_dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for idx in page_indices:
            if idx < 0 or idx >= doc.page_count:
                warnings.append(f"skip_invalid_page:{idx}")
                continue
            page = doc.load_page(idx)
            text = page.get_text("text") or ""
            text_parts.append(text)
            rect = page.rect
            pages_out.append(
                {
                    "page_number": idx + 1,
                    "width": rect.width,
                    "height": rect.height,
                    "text_length": len(text.strip()),
                    "bbox": [0, 0, rect.width, rect.height],
                }
            )
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")
            saved = self.store.save_bytes(
                png_bytes,
                kind="documents",
                category="rendered_pages",
                suffix=f"_p{idx + 1}.png",
                source_path=path,
                request_id=request.request_id,
                extra={"page": idx + 1},
            )
            rendered.append(saved["path"])

        doc.close()
        return pages_out, rendered, text_parts, warnings

    def _parse_fixture(self, path: Path, request: PdfParseRequest) -> tuple[list, list, list, list]:
        data = path.read_bytes()
        page_count = max(1, data.count(b"/Type /Page"))
        pages_out = []
        text_parts = []
        for i in range(page_count):
            pages_out.append(
                {
                    "page_number": i + 1,
                    "width": 612,
                    "height": 792,
                    "text_length": 0,
                    "bbox": [0, 0, 612, 792],
                    "fixture": True,
                }
            )
            text_parts.append(f"[fixture page {i + 1} text placeholder]")
        return pages_out, [], text_parts, ["pymupdf_not_installed"]

    def render_page(self, path: Path, page: int, dpi: int = 150) -> dict[str, Any]:
        req = PdfParseRequest(input_path=str(path), pages=[page - 1], render_dpi=dpi)
        artifact = self.parse_pdf(req)
        if artifact.rendered_page_paths:
            return {"path": artifact.rendered_page_paths[0], "page": page}
        return {"path": None, "page": page, "warnings": artifact.warnings}
