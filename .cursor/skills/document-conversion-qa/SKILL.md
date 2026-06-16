---
name: document-conversion-qa
description: >-
  QA markitdown conversion output against source — missing pages, broken tables,
  low OCR confidence. Use after document-intake. Recommend visual re-check when
  figures/equations matter.
---

# Document Conversion QA

## Checks

1. Output file exists and non-empty
2. Heading count vs source page count (heuristic)
3. Table rows — flag if pipe-table obviously truncated
4. Record `limitations[]` for PDF scan quality, PPTX slide loss, XLSX sheet names only

## Verdict

PASS | PASS_WITH_LIMITATIONS | FAIL

Pair with `research-integrity-guard` for academic content.
