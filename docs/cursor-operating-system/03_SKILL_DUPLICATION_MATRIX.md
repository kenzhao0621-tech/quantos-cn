# Skill Duplication Matrix

Inherited from `docs/cursor-skills/02_DUPLICATION_MATRIX.md` with OS extensions.

## Resolved duplicates

| A | B | Overlap | Decision |
|---|---|---------|----------|
| Superpowers | brainstorming/writing-plans | high | USE_AS_SUBSKILL |
| requesting-code-review | code-review | high | adapter |
| systematic-debugging | debug-radar | high | adapter |
| TDD + webapp-testing | test-pilot | medium | adapter |
| verification-before-completion | ship-checklist | medium | adapter |
| create-skill (built-in) | skill-creator | high | KEEP_EXISTING |
| webapp-testing | playwright-scout | 60% | alias → primary |
| code-simplifier | refactor-lens | 50% | lens UNRESOLVED |
| ui-ux-pro-max | frontend-design | 40% | split research vs impl |
| impeccable | frontend-design | 30% | polish stage only |
| agent-reach | serper/last30days | 35% | defer Phase 2 |
| ralph-loop | nightly-runner | 35% | runner UNRESOLVED |

## New OS skills (no overlap)

image-analysis-router, web-content-safety-gate, licensed-media-finder — unique gates/routers

## Rule

One primary + at most one fallback per capability. See `06_SKILL_ROUTING.md`.
