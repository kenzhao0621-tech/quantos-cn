---
name: citation-graph-builder
description: >-
  Build citation graph from References section and in-text citations in local
  Markdown. No external API required. Optional Semantic Scholar adapter disabled
  until API key configured. Do NOT invent citations.
---

# Citation Graph Builder

## Local-only

1. Parse References section into nodes `{id, title, authors, year}` when parseable.
2. Parse in-text citations `[n]` or `(Author, year)` patterns.
3. Classify edges: foundational, related, competing (manual tags only with evidence).

## With API (disabled by default)

If `SEMANTIC_SCHOLAR_API_KEY` set → see `docs/integrations/semantic-scholar.md` (template).

Output: `docs/test-output/papers/<hash>/citation-graph.json`

Mark `unavailable_evidence: external graph enrichment` when API off.
