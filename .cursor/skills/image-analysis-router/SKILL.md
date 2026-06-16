---
name: image-analysis-router
description: >-
  Classify local images (UI screenshot, document scan, chart, diagram, photo,
  terminal capture) and route to the correct analysis pipeline. Use when the
  user uploads or references an image file and analysis type is unclear. Do NOT
  use for pure text documents or when webapp-testing already owns a live URL.
---

# Image Analysis Router

## Classification (pick one)

| Type | Signals | Route to |
|------|---------|----------|
| UI screenshot | browser chrome, components, layout | webapp-testing + visual review + optional Screenshot QA |
| Website screenshot | full page, URL context | Playwright re-capture if URL known; else visual + DOM if available |
| Scanned document | page skew, text blocks | markitdown/OCR; preserve page map |
| Academic figure | caption, axes, figure number | paper figure-table workflow (Phase 3) |
| Table image | grid lines, headers | OCR + structured table extraction |
| Chart | axes, legend, data marks | Describe axes/units/trend; do not invent numeric values |
| Diagram | boxes, arrows, labels | mermaid-renderer comparison if source exists |
| Photograph | camera metadata, natural scene | Describe only visible content |
| Design mockup | Figma-like, spacing tokens | ui-ux-pro-max + frontend-design |
| Error screenshot | stack trace, dialog | systematic-debugging |
| Terminal screenshot | monospace, prompt | systematic-debugging; extract command output only |
| Architecture drawing | layered boxes, services | diagram-architect review |

## Required process

1. Inspect file path, extension, MIME (do not trust extension alone).
2. Record width, height, byte size; refuse processing if over project limit (default 20MB).
3. Classify using table above; state confidence (high/medium/low).
4. If OCR needed: note language assumption and low-confidence regions.
5. If DOM available (URL + Playwright): prefer DOM/a11y tree over pixel guess.
6. Output structured findings with region references; mark unreadable areas explicitly.
7. Never claim text was read when OCR confidence is low.

## Negative triggers

- User only wants code changes with no image input
- Licensed stock photo download (use `licensed-media-finder`)
- Generative image creation (use GenerateImage only when explicitly requested)

## Outputs

```text
Classification: <type> (confidence: high|medium|low)
Dimensions: WxH, size
Pipeline: <primary skill(s)>
Findings: ...
Uncertainties: ...
Next step: ...
```
