---
name: paper-structure-analyzer
description: >-
  Detect academic paper sections (Abstract, Introduction, Methods, Results, etc.)
  from Markdown converted by markitdown. Use after paper-intake. Local only — no
  paid APIs. Record page references when markitdown preserves page breaks.
---

# Paper Structure Analyzer

## Detect (when present)

Abstract, Introduction, Background, Related Work, Methodology, Model Architecture, Algorithms, Experimental Setup, Datasets, Evaluation Metrics, Results, Ablation Studies, Discussion, Limitations, Ethics, Conclusion, References, Appendices

## Output

```yaml
sections:
  - name: Introduction
    start_line: 42
    page_hint: 2
    confidence: medium
gaps:
  - "No explicit Methods heading — possible merge with Section 3"
```

Use heading hierarchy from Markdown; mark `confidence: low` when headings ambiguous.

Negative: non-academic docs → document-intake only.
