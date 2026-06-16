---
name: research-integrity-guard
description: >-
  Final gate for research outputs — block invented DOI, authors, page numbers,
  citations, or results. Use before delivering paper analysis. FAIL if any claim
  lacks evidence type label.
---

# Research Integrity Guard

## Never allow

- Invented paper, author, DOI, page, citation, experimental result
- Abstract-only inference presented as full-paper conclusion
- Model inference presented as direct quotation

## Required on every major claim

```yaml
paper: ""
section: ""
page: ""
evidence: source_text | extracted_fact | summary | inference
confidence: high | medium | low
```

## Verdict

PASS | PASS_WITH_LIMITATIONS | FAIL (list violations)
