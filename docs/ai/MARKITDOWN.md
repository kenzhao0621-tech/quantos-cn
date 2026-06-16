# MarkItDown installation

| Field | Value |
|-------|-------|
| Venv | `.venv-markitdown/` (gitignored) |
| Python | 3.11 |
| Package | `markitdown[all]==0.1.2` |
| CLI | `.venv-markitdown/bin/markitdown` |
| Pins | `docs/ai/requirements-markitdown-pins.txt` |

## Smoke tests (2026-06-16)

| Format | Result |
|--------|--------|
| TXT | PASS |
| HTML | PASS |
| DOCX | PASS |
| PPTX | PASS |
| XLSX | PASS |
| PDF | PASS (minimal fixture) |

Outputs: `docs/test-output/` (gitignored). Originals preserved in `docs/test-fixtures/`.

## Limitations

- Complex PDFs may lose layout/tables — use `document-conversion-qa`
- Azure Document Intelligence disabled (paid)
- Audio/YouTube not tested in this batch

## Rollback

```bash
rm -rf .venv-markitdown
```
