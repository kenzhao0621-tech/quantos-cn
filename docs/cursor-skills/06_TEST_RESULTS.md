# Test Results (Round 2)

## Combination tests

| Test | Result | Notes |
|------|--------|-------|
| A: New feature pipeline order | PASS | Routing doc enforces stage separation |
| B: Frontend pipeline order | PASS | ui-ux-pro-max → frontend-design → impeccable |
| C: CI failure routing | PASS | ci-fixer primary; debug-radar secondary |
| D: Refactor pipeline | PASS_WITH_LIMITATIONS | Refactor Lens UNRESOLVED; code-simplifier installed |
| E: Ralph loop safety | PASS | disabled-by-default; max_iterations in skill text |
| E: Agent Swarm | PASS | Not installed |
| E: Nightly Runner | PASS | Not installed |

## New installs — per skill

| Skill | Positive | Negative | Functional | Overall |
|-------|----------|----------|------------|---------|
| planning-with-files | PASS | PASS | PASS — SKILL.md + templates | PASS |
| superpowers router | PASS | PASS | PASS | PASS |
| webapp-testing | PASS | PASS | PASS_WITH_LIMITATIONS — Playwright not verified | PASS_WITH_LIMITATIONS |
| code-simplifier | PASS | PASS | PASS | PASS |
| mcp-builder | PASS | PASS | PASS | PASS |
| pptx | PASS | PASS | PASS_WITH_LIMITATIONS — pptx lib not run | PASS_WITH_LIMITATIONS |
| context-pack | PASS | PASS | PASS_WITH_LIMITATIONS — CLI optional | PASS_WITH_LIMITATIONS |
| repo-cartographer | PASS | PASS | PASS | PASS |
| ci-fixer | PASS | PASS | PASS | PASS |
| ui-ux-pro-max | PASS | PASS | PASS — data/scripts copied | PASS |
| impeccable | PASS | PASS | PASS | PASS |
| agent-reach | PASS | PASS | BLOCKED exec | BLOCKED_BY_CREDENTIAL |
| ralph-loop | PASS | PASS | PASS — disabled default | PASS_WITH_LIMITATIONS |
| code-review adapter | PASS | PASS | PASS | PASS |
| debug-radar adapter | PASS | PASS | PASS | PASS |
| test-pilot adapter | PASS | PASS | PASS | PASS |
| ship-checklist adapter | PASS | PASS | PASS | PASS |
| Superpowers subskills (10) | PASS | PASS | PASS — frontmatter valid | PASS |

## Cursor discovery

- **33** project skill directories with `SKILL.md` — **PASS**
- Name/dir mismatches: 0 — **PASS**

## Cross-skill conflict

- brainstorming vs writing-plans vs planning-with-files: descriptions narrowed — **PASS**
- ui-ux-pro-max vs frontend-design vs impeccable: narrowed — **PASS**
- built-in review vs code-review: complementary — **PASS**
