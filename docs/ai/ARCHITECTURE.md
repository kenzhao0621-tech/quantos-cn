# Architecture — Cursor OS (netlify-demo)

## Project application

Static marketing/demo site deployed via **Netlify** with optional **Netlify Functions** (`@netlify/functions`, `netlify-cli`).

```
netlify-demo/
├── index.html, thank-you.html    # static pages
├── netlify.toml                  # deploy config
├── netlify/functions/            # serverless (if present)
├── package.json                  # netlify dev/deploy scripts
└── .cursor/                      # agent tooling (not deployed)
```

## Agent tooling architecture (seven layers)

```mermaid
flowchart TB
  subgraph LayerA [Layer A — Orchestration]
    SP[Superpowers]
    PWF[Planning with Files]
    CP[Context Pack]
    RL[Ralph Loop disabled]
  end
  subgraph LayerB [Layer B — Engineering]
    RC[Repo Cartographer]
    FE[Frontend Design]
    WT[Webapp Testing]
    CI[CI Fixer]
  end
  subgraph LayerC [Layer C — Design]
    UUX[UI UX Pro Max]
    IMP[Impeccable]
  end
  subgraph LayerD [Layer D — Web Research]
    AR[Agent Reach]
    WSG[Web Content Safety Gate]
  end
  subgraph LayerE [Layer E — Documents]
    MD[MarkItDown]
    IAR[Image Analysis Router]
  end
  subgraph LayerG [Layer G — Delivery]
    SC[Ship Checklist]
  end
  LayerA --> LayerB
  LayerB --> LayerC
  LayerD --> LayerE
  LayerB --> LayerG
```

## Scope boundaries

| Concern | Project repo | User global |
|---------|--------------|-------------|
| Skills | `.cursor/skills/` | `~/.cursor/skills/` |
| Hooks | `.cursor/hooks.json` | — |
| MCP | `.cursor/mcp.json` (future) | `~/.cursor/mcp.json` |
| Secrets | never committed | env / keychain |

## Routing entrypoints

- Project: `.cursor/skills/SKILL_ROUTING.md`
- OS: `docs/cursor-operating-system/06_SKILL_ROUTING.md`
