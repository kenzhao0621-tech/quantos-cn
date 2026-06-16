# Plugin and MCP Audit

**Date**: 2026-06-16

## MCP servers

| Server | Scope | Status | Notes |
|--------|-------|--------|-------|
| (none) | project | — | `.cursor/mcp.json` absent |
| (none) | user | — | `~/.cursor/mcp.json` absent |
| cursor-ide-browser | Cursor built-in | ACTIVE | Browser automation in agent |
| cursor-app-control | Cursor built-in | ACTIVE | IDE control |

## Planned (credential-gated)

| Server | Phase | Credential |
|--------|-------|------------|
| Figma official MCP | 1 | Figma token (env) |
| Firecrawl MCP | 2 | API key |
| Serper | 2 | SERPER_API_KEY |
| Playwright MCP | 1–2 | optional |
| Exa (via mcporter) | 2 | Exa MCP config |

## Plugins

No Cursor marketplace plugins installed in repo. Ralph-loop hooks sourced from `cursor/plugins` (pinned scripts in `.cursor/hooks/`).

## Audit actions

- Do not add MCP entries with embedded secrets
- Run `gh skill preview` pattern mentally: read SKILL.md + scripts before install
- Phase 2 adds Firecrawl/Serper only after web-content-safety-gate is active
