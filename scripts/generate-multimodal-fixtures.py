#!/usr/bin/env python3
"""Generate deterministic multimodal test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "docs" / "test-fixtures" / "multimodal"
FIX.mkdir(parents=True, exist_ok=True)

# sample.png
try:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (128, 128), (40, 80, 160))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 108, 60], fill=(255, 255, 255))
    draw.text((30, 30), "SAMPLE", fill=(0, 0, 0))
    img.save(FIX / "sample.png")
except ImportError:
    (FIX / "sample.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

# sample_digital.pdf
pdf_path = FIX / "sample_digital.pdf"
try:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Multimodal Sample PDF", fontsize=14)
    page.insert_text((72, 100), "Page 1 — digital text layer for triage tests.")
    doc.save(pdf_path)
    doc.close()
except ImportError:
    try:
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(pdf_path))
        c.drawString(72, 720, "Multimodal Sample PDF")
        c.drawString(72, 700, "Page 1 — digital text layer for triage tests.")
        c.showPage()
        c.save()
    except ImportError:
        # Minimal valid single-page PDF
        pdf_path.write_bytes(
            b"%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
            b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
            b"4 0 obj<< /Length 44 >>stream\nBT /F1 12 Tf 72 720 Td (Sample PDF) Tj ET\nendstream\nendobj\n"
            b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
            b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \n0000000261 00000 n \n0000000354 00000 n \n"
            b"trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n427\n%%EOF\n"
        )

expected = {
    "sample_png": {"width": 128, "height": 128, "format": "PNG"},
    "sample_digital_pdf": {"min_pages": 1, "digital_or_scanned": ["digital", "unknown"]},
    "fixture_provider_seed": 42,
}
(FIX / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")

print(f"Fixtures written to {FIX}")
