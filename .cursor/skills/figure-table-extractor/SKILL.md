---
name: figure-table-extractor
description: >-
  Extract figure and table captions and structured descriptions from paper Markdown.
  Use when figures/tables matter. Mark numeric values as extracted_fact only when
  visible in text; never invent data from charts.
---

# Figure & Table Extractor

Per figure/table:

- number, caption, page_hint
- purpose, variables, units
- main_result
- interpretation (**explicit** from caption vs **inferred**)
- limitations (resolution, OCR gaps)

If markitdown lost table structure, record `extraction_warning: table may be incomplete`.
