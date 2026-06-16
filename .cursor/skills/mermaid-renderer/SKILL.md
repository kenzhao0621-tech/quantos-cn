---
name: mermaid-renderer
description: >-
  Render Mermaid diagram source files to SVG/PNG using @mermaid-js/mermaid-cli.
  Use after diagram-architect or when .mmd files exist. BLOCKED if mmdc not
  installed — suggest npx @mermaid-js/mermaid-cli. Do NOT use for data charts
  that need real datasets.
---

# Mermaid Renderer

## Prerequisites

```bash
npm install -D @mermaid-js/mermaid-cli
# or: npx @mermaid-js/mermaid-cli -i diagram.mmd -o diagram.svg
```

## Render

```bash
npx @mermaid-js/mermaid-cli -i docs/diagrams/NAME.mmd -o docs/diagrams/NAME.svg
```

## Rules

- Input must be tracked `.mmd` source — not hand-drawn bitmaps
- Re-render after source edits; commit both source and output if team policy requires
- If render fails, fix syntax in source; do not substitute generative images

## Status

**WORKING** — `@mermaid-js/mermaid-cli` installed as devDependency; use `npm run diagram:render` or `npx mmdc`.
