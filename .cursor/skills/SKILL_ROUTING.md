# Skill Routing (Project)

See also: `docs/cursor-skills/05_SKILL_ROUTING.md`

## Superpowers sub-skills (do not duplicate)

| Sub-skill | Stage |
|-----------|-------|
| brainstorming | Ideation |
| context-pack | One-shot context |
| writing-plans | Implementation plan |
| planning-with-files | Long-running state |
| executing-plans / subagent-driven-development | Execute |
| test-driven-development | TDD |
| systematic-debugging | Debug (debug-radar routes here) |
| requesting-code-review / receiving-code-review | Review (code-review routes here) |
| verification-before-completion | Verify (ship-checklist routes here) |

## Disabled by default

- **ralph-loop** — requires explicit authorization + max_iterations

## BLOCKED execution

- **agent-reach** — install definition only; needs CLI + credentials

## Release & deps

| Task | PRIMARY |
|------|---------|
| Changelog / release notes | release-docs |
| Pre-install dep scan | ci-fixer + npm audit; FALLBACK dependency-guard |

## Research (Phase 3)

paper-intake → paper-structure-analyzer → section-by-section-reader → figure-table-extractor → citation-graph-builder → research-synthesis → research-integrity-guard

document-intake → markitdown (`.venv-markitdown/bin/markitdown`) → document-conversion-qa

## Refactor

repo-cartographer → refactor-lens (FALLBACK) → code-simplifier

## OS routers (Phase 1)

| Task | PRIMARY |
|------|---------|
| Classify image input | image-analysis-router |
| Sanitize web fetch | web-content-safety-gate |
| Licensed stock photos | licensed-media-finder |
| Architecture diagrams | diagram-architect → mermaid-renderer |

See `docs/cursor-operating-system/06_SKILL_ROUTING.md`.

## PRIMARY quick reference

| Task | PRIMARY |
|------|---------|
| Find skills | find-skills |
| Design research | ui-ux-pro-max |
| Build UI | frontend-design |
| Polish UI | impeccable |
| E2E test | webapp-testing |
| CI fix | ci-fixer |
| Simplify code | code-simplifier |
| Repo map | repo-cartographer |
| MCP server | mcp-builder |
| Create skill | create-skill (built-in) |
