"""PDF triage — writes PDF_TRIAGE.json and PDF_TRIAGE.md."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def triage_pdf(input_path: Path, output_dir: Optional[Path] = None) -> dict[str, Any]:
    """Classify PDF and write triage artifacts."""
    path = Path(input_path).resolve()
    out_dir = (output_dir or path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "source_path": str(path),
        "source_name": path.name,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "encrypted": False,
        "page_count": 0,
        "digital_or_scanned": "unknown",
        "text_coverage": 0.0,
        "embedded_images": 0,
        "table_density": "low",
        "formula_density": "low",
        "multi_column": False,
        "language": "unknown",
        "recommended_engines": ["fixture"],
        "warnings": [],
    }

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(path)
        result["page_count"] = doc.page_count
        result["encrypted"] = doc.is_encrypted
        text_chars = 0
        images = 0
        for i in range(doc.page_count):
            page = doc.load_page(i)
            text = page.get_text("text") or ""
            text_chars += len(text.strip())
            images += len(page.get_images(full=True))
        doc.close()

        avg_text = text_chars / max(1, result["page_count"])
        result["text_coverage"] = min(1.0, avg_text / 500.0)
        result["embedded_images"] = images
        result["digital_or_scanned"] = "digital" if result["text_coverage"] > 0.2 else "scanned"
        result["recommended_engines"] = ["pymupdf", "docling", "paddleocr"]
        if result["digital_or_scanned"] == "scanned":
            result["recommended_engines"] = ["paddleocr", "pymupdf"]
    except ImportError:
        result["warnings"].append("pymupdf_not_installed_using_fixture_triage")
        result = _fixture_triage(path, result)
    except Exception as exc:
        result["warnings"].append(f"triage_error:{type(exc).__name__}")
        result = _fixture_triage(path, result)

    json_path = out_dir / "PDF_TRIAGE.json"
    md_path = out_dir / "PDF_TRIAGE.md"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    md_path.write_text(_triage_markdown(result), encoding="utf-8")

    result["triage_json_path"] = str(json_path)
    result["triage_md_path"] = str(md_path)
    return result


def _fixture_triage(path: Path, base: dict[str, Any]) -> dict[str, Any]:
    data = path.read_bytes()
    base["page_count"] = max(1, data.count(b"/Type /Page"))
    base["digital_or_scanned"] = "digital" if b"/Font" in data else "unknown"
    base["text_coverage"] = 0.5 if b"/Font" in data else 0.05
    base["recommended_engines"] = ["fixture", "pymupdf"]
    return base


def _triage_markdown(triage: dict[str, Any]) -> str:
    lines = [
        "# PDF Triage",
        "",
        f"- **Source:** `{triage.get('source_name', '')}`",
        f"- **Pages:** {triage.get('page_count', 0)}",
        f"- **Type:** {triage.get('digital_or_scanned', 'unknown')}",
        f"- **Encrypted:** {triage.get('encrypted', False)}",
        f"- **Text coverage:** {triage.get('text_coverage', 0):.2f}",
        f"- **Embedded images:** {triage.get('embedded_images', 0)}",
        f"- **Recommended engines:** {', '.join(triage.get('recommended_engines', []))}",
        "",
    ]
    if triage.get("warnings"):
        lines.append("## Warnings")
        for w in triage["warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"
