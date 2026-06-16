---
name: document-intake
description: >-
  Intake documents for processing — hash, metadata, page count, format detection.
  Use at start of any document or paper pipeline. Never overwrite originals.
  Outputs go to docs/test-output/ or user-specified staging dir. Works with
  markitdown CLI in .venv-markitdown. Do NOT use for web URLs (use agent-reach).
---

# Document Intake

## Steps

1. Record `filename`, absolute path, byte size, MIME (file command / extension hint).
2. Compute SHA-256: `shasum -a 256 <file>`
3. Copy original to staging unchanged (optional `docs/intake/originals/`).
4. Record page/slide count when available (PDF/DOCX/PPTX).
5. Route by extension:
   - `.md`, `.txt`, `.html`, `.csv`, `.json` → direct or markitdown
   - `.pdf`, `.docx`, `.pptx`, `.xlsx` → markitdown via project venv
6. Emit intake record (JSON):

```json
{
  "filename": "",
  "sha256": "",
  "format": "",
  "pages": null,
  "conversion_status": "pending|done|unsupported",
  "warnings": []
}
```

## Tool

```bash
.venv-markitdown/bin/markitdown <file> -o docs/test-output/<basename>.md
```

Preserve originals; write outputs only to output directory.
