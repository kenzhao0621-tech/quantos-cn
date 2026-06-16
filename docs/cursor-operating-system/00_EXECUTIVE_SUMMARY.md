# Cursor Engineering & Research OS — Executive Summary

**Audit date**: 2026-06-16  
**Phase**: 0 complete → Phase 1 in progress  
**Project**: netlify-demo  
**Branch**: `chore/cursor-operating-system`  
**Prior branch**: `chore/cursor-skills-audit` (2 commits)  
**Overall status**: PASS_WITH_LIMITATIONS

## Phase 0 outcomes

| Item | Value |
|------|-------|
| CWD / Git root | `/Users/kenzhao/Projects/netlify-demo` |
| Cursor CLI | v22.22.1 |
| Node | v22.22.3 |
| Python | 3.9.6 system; 3.11.15 (uv) for agent-reach venv |
| Framework | Static site + Netlify Functions (`netlify-cli`) |
| Project skills | 33 (+ `SKILL_ROUTING.md`) |
| User skills (`~/.cursor/skills/`) | 35 (globalized 2026-06-16) |
| Built-in skills (`skills-cursor/`) | 18 |
| MCP servers | 0 (project + user) |
| Rules | 0 |
| Custom agents | 0 (Phase 4 will add) |
| Hooks | 2 scripts + `hooks.json` (ralph-loop) |
| Backup | `.cursor-backups/os-audit-20260616-152306/` |
| Prior backup | `.cursor-backups/skills-audit-20260616-143447/` |

## Capability layers (current)

| Layer | Primary | Status |
|-------|---------|--------|
| A Orchestration | Superpowers, planning-with-files, context-pack | WORKING |
| B Engineering | repo-cartographer, code-simplifier, ci-fixer, webapp-testing | WORKING |
| C Design/Visual | ui-ux-pro-max, frontend-design, impeccable | WORKING |
| D Web research | agent-reach | BLOCKED_BY_CREDENTIAL (partial: web/rss/v2ex ok) |
| E Document intel | markitdown | BLOCKED_BY_DEPENDENCY (CLI not installed) |
| F Academic research | — | UNVERIFIED (Phase 3) |
| G Delivery | ship-checklist adapters | WORKING; release/changelog UNRESOLVED |

## Duplicates resolved (prior audit)

- Superpowers sub-skills: single install, thin adapters for code-review/debug-radar/test-pilot/ship-checklist
- skill-creator → KEEP_EXISTING built-in `create-skill`
- brainstorming/writing-plans → USE_AS_SUBSKILL (not second copies)

## First safe installation batch (Phase 1)

Local markdown-only routers (no credentials, reversible):

1. `image-analysis-router` — classify & route image inputs
2. `web-content-safety-gate` — prompt-injection quarantine for crawled content
3. `licensed-media-finder` — workflow + asset ledger schema
4. `diagram-architect` / `mermaid-renderer` — reproducible diagrams (CLI when available)
5. Subagent definitions under `.cursor/agents/` (documentation-only until Phase 4)

Deferred (credentials / upstream hunt):

- Figma MCP, Firecrawl, Serper, Last30Days, Screenshot QA upstream, markitdown CLI

See `01_ENVIRONMENT_INVENTORY.md`, `05_INSTALLATION_DECISIONS.md`, `19_BLOCKED_AND_UNRESOLVED.md`.
