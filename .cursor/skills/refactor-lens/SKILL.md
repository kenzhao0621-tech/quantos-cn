---
name: refactor-lens
description: >-
  Analyze legacy code for safe refactor entry points before editing (Refactor Lens).
  FALLBACK adapter to peizh/refactor-legacy-code. Use when mapping refactor hotspots,
  characterization tests, or dependency seams in poorly tested code. PRIMARY execute
  path remains code-simplifier; PRIMARY map remains repo-cartographer. Do NOT use
  for greenfield features or when code-simplifier alone suffices.
---

# Refactor Lens

**Adapter** — upstream: [peizh/refactor-legacy-code](https://github.com/peizh/refactor-legacy-code) @ `2296d9b3f20d46658f2cf8f9a4ba4d8be26d7c65`

## Routing

| Stage | Skill |
|-------|-------|
| Map structure | `repo-cartographer` (PRIMARY) |
| Analyze legacy risk / seams | **refactor-lens** (this skill) |
| Execute cleanup | `code-simplifier` (PRIMARY) |

## Workflow

1. Run `repo-cartographer` if structure is unknown.
2. Load and follow `references/upstream-SKILL.md` and `references/*.md` for the legacy refactor loop.
3. Hand off execution to `code-simplifier` only after characterization tests or proof contract exists.

## Negative triggers

- Small, well-tested refactors → `code-simplifier` only
- Greenfield implementation → `frontend-design` / TDD

See `SOURCE.md` for audit record.
