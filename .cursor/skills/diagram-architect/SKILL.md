---
name: diagram-architect
description: >-
  Plan reproducible architecture, sequence, flow, and research-method diagrams
  using Mermaid or code-based charts. Use when the user needs system diagrams,
  ERDs, deployment views, or method figures — not generative art. Prefer source
  files over one-off images.
---

# Diagram Architect

## Tool selection

| Need | Tool | Skill |
|------|------|-------|
| Architecture, sequence, flow, ERD, state | Mermaid source | `mermaid-renderer` |
| Quantitative charts | Matplotlib/Plotly/Recharts | code in repo |
| Publication figure QA | Manual review checklist | this skill |

## Workflow

1. Clarify audience and diagram type.
2. Draft **Mermaid source** in `docs/diagrams/<name>.mmd` (or project convention).
3. List entities, relationships, and labels — no invented metrics.
4. Hand off to `mermaid-renderer` for PNG/SVG if CLI available.
5. Version-control the `.mmd` file; rendered output is derivative.

## Quality bar

- Every box/edge has a clear label
- Title and legend when needed
- No fabricated data in charts
- Revision-friendly text source always checked in

## Negative triggers

- UI mockups → ui-ux-pro-max + frontend-design
- Screenshot comparison → webapp-testing / screenshot-qa
