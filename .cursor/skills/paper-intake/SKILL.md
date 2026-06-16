---
name: paper-intake
description: >-
  Ingest academic papers (PDF, arXiv exports) with metadata, DOI, section map stub,
  and file hash. No paid APIs. Use before paper-structure-analyzer. Mark unavailable
  full text clearly. Do NOT invent DOI or authors.
---

# Paper Intake

## Output schema

- title, authors, year, venue (if visible on first pages)
- doi (only if printed in document — else `null`)
- url or arxiv id (if in filename/metadata)
- file_hash (SHA-256)
- page_count
- section_map: `[]` until structure-analyzer runs
- conversion_status
- missing_content_warnings: []

## Procedure

1. Run `document-intake`.
2. Convert with markitdown; store under `docs/test-output/papers/<hash>/`.
3. Extract title from first heading or mark `uncertainty: high`.
4. For arXiv IDs in filename (`YYMM.NNNNN`), record id — do not fetch API unless user enables Phase 2 adapters.

## Evidence types

| Field | Type |
|-------|------|
| Visible metadata | extracted_fact |
| Crossref lookup | unavailable unless API configured |
| Guessed venue | inference (forbidden without label) |
