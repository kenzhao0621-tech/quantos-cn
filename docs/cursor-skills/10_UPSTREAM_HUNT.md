# Upstream Hunt — 14 UNRESOLVED Screenshot Skills

**Date**: 2026-06-16  
**Method**: GitHub/code search, skills.sh registry, agent-skills.md index, semantic overlap vs installed skills.  
**Bar for INSTALL**: exact name match OR ≥2 verification signals (README + SKILL.md + license + recent commits) + semantic fit ≥60%.

## Summary

| Screenshot name | Verdict | Best candidate | Overlap | Recommended action |
|-----------------|---------|----------------|---------|-------------------|
| Refactor Lens | NEED_USER_CONFIRMATION | `peizh/refactor-legacy-code` | 72% | Install as fallback; keep `code-simplifier` primary |
| API Stitcher | UNRESOLVED | — | — | Author local skill or use `mcp-builder` |
| Migration Buddy | NEED_USER_CONFIRMATION | `sickn33/.../legacy-modernizer` | 68% | Install adapter; overlaps `executing-plans` |
| Docs Whisperer | NEED_USER_CONFIRMATION | `majiayu000/.../docs-seeker` | 55% | Partial fit; pair with `markitdown` |
| Prompt Harness | UNRESOLVED | — | — | No canonical upstream |
| Agent Swarm | NEED_USER_CONFIRMATION | `uthunderbird/swarm-skill` | 50% | Different semantics (critique swarm) |
| Playwright Scout | NEED_USER_CONFIRMATION | `anthropics/skills` webapp-testing (installed) | 65% | Use installed `webapp-testing` |
| Terminal Sense | NEED_USER_CONFIRMATION | `obra/superpowers/systematic-debugging` (installed) | 45% | Use installed; no log-parser skill found |
| Release Notes | NEED_USER_CONFIRMATION | `alibaba/page-agent` `update-changelog` | 70% | Install if user confirms |
| Data Cleaner | UNRESOLVED | `daymade/docs-cleaner` (docs only) | 25% | Wrong domain — not tabular data |
| Screenshot QA | NEED_USER_CONFIRMATION | `maxrihter/claude-skill-visual-regression` | 75% | Install for visual regression |
| Changelog Miner | NEED_USER_CONFIRMATION | `CuriousLearner/devkit/changelog-generator` | 65% | Overlaps release-notes candidate |
| Dependency Guard | NEED_USER_CONFIRMATION | `aptratcn/skill-dependency-guard` | 80% | **Archived** repo; markdown-only |
| Nightly Runner | UNRESOLVED | — | — | No skill; use CI/cron with explicit auth |

---

## 1. Refactor Lens (`refactor-lens`)

**Screenshot intent**: Analyze codebase for refactor hotspots before editing (lens / map, not execute).

**Exact-name search**: 0 repos with `refactor-lens` SKILL.md.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [peizh/refactor-legacy-code](https://github.com/peizh/refactor-legacy-code) | README ✓ SKILL.md ✓ MIT ✓ skills.sh ✓ | 72% | Safe legacy refactor workflow; characterization tests |
| [kreek/consult `refactoring`](https://github.com/kreek/consult) | SKILL.md ✓ | 65% | Behavior-preserving patterns, Mikado/strangler |
| [vasilyu1983/AI-Agents-public `qa-refactoring`](https://github.com/vasilyu1983/AI-Agents-public) | SKILL.md ✓ references/ ✓ | 60% | QA-focused refactor catalog |
| [Zpankz/refactor](https://github.com/Zpankz/refactor) | SKILL.md ✓ scripts ✓ tests ✓ | 40% | Graph/module decomposition — different goal |

**Installed overlap**: `code-simplifier` (execute cleanup), `repo-cartographer` (map structure).

**Recommendation**: `NEED_USER_CONFIRMATION` → install `peizh/refactor-legacy-code` as **refactor-lens fallback** adapter, or extend `repo-cartographer` routing.

---

## 2. API Stitcher (`api-stitcher`)

**Screenshot intent**: Wire multiple APIs / stitch OpenAPI + client glue.

**Exact-name search**: 0 canonical SKILL.md.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [anthropics/skills `mcp-builder`](https://github.com/anthropics/skills) (installed) | ✓ | 35% | MCP servers, not REST stitching |
| [vercel-labs skills](https://github.com/vercel-labs/agent-skills) | partial | 30% | No api-stitcher name |

**Recommendation**: **UNRESOLVED** — likely screenshot-only branding. Use `mcp-builder` + manual OpenAPI workflow until user provides source URL.

---

## 3. Migration Buddy (`migration-buddy`)

**Screenshot intent**: Framework/version migration assistant.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [sickn33/antigravity-awesome-skills `legacy-modernizer`](https://github.com/sickn33/antigravity-awesome-skills) | SKILL.md ✓ community | 68% | jQuery→React, strangler fig |
| [tech-leads-club/agent-skills `legacy-migration-planner`](https://github.com/tech-leads-club/agent-skills) | registry entry | 60% | Planner not buddy |
| [peizh/refactor-legacy-code](https://github.com/peizh/refactor-legacy-code) | ✓ | 55% | Refactor not migration |

**Installed overlap**: `executing-plans`, Superpowers migration patterns.

**Recommendation**: `NEED_USER_CONFIRMATION` → `legacy-modernizer` or author thin `migration-buddy` adapter.

---

## 4. Docs Whisperer (`docs-whisperer`)

**Screenshot intent**: Improve / generate developer documentation from code.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [majiayu000/claude-skill-registry `docs-seeker`](https://github.com/majiayu000/claude-skill-registry) | SKILL.md ✓ | 55% | **Discovery** not authoring |
| [daymade/claude-code-skills `docs-cleaner`](https://github.com/daymade/claude-code-skills) | SKILL.md ✓ | 50% | Consolidation not whisper |
| [coroboros/markitdown](https://github.com/microsoft/markitdown) (installed skill) | ✓ | 40% | Convert docs formats |

**Low-signal**: 1 repo mentioning "docs-whisperer" in issues only (not SKILL.md).

**Recommendation**: `NEED_USER_CONFIRMATION` — no exact match; combine `markitdown` + optional `docs-seeker`.

---

## 5. Prompt Harness (`prompt-harness`)

**Screenshot intent**: Test/evaluate prompt variants systematically.

**Exact-name search**: 0 SKILL.md named `prompt-harness`.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [harness/harness-skills](https://github.com/harness/harness-skills) | org name collision | 15% | CI/CD, not prompt eval |
| Exercise stubs (panaversity) | tutorial only | 20% | Not production skill |

**Recommendation**: **UNRESOLVED** — requires screenshot source or user-authored skill.

---

## 6. Agent Swarm (`agent-swarm`)

**Screenshot intent**: Parallel multi-agent execution.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [uthunderbird/swarm-skill](https://github.com/uthunderbird/swarm-skill) | README ✓ 4 skills ✓ | 50% | **Critique/red-team** swarm, not parallel coding |
| [obra/superpowers `subagent-driven-development`](https://github.com/obra/superpowers) (installed) | ✓ | 45% | Controlled subagents |
| Trigger.dev `trigger-agents` | docs only | 35% | Orchestration platform |

**Recommendation**: `NEED_USER_CONFIRMATION` — high risk; if installed use `subagent-driven-development` first. Do not install `swarm-skill` without user review (different semantics).

---

## 7. Playwright Scout (`playwright-scout`)

**Screenshot intent**: Explore UI with Playwright (scout / recon).

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| **Installed `webapp-testing`** | anthropics ✓ | 65% | Browser automation + testing |
| [maxrihter/claude-skill-visual-regression](https://github.com/maxrihter/claude-skill-visual-regression) | SKILL.md ✓ CI workflows ✓ | 55% | Regression not exploration |
| [jmagly/aiwg `regression-visual`](https://github.com/jmagly/aiwg) | SKILL.md ✓ | 50% | Visual diff focus |

**Recommendation**: Route to **installed `webapp-testing`**; mark screenshot name as alias in routing doc.

---

## 8. Terminal Sense (`terminal-sense`)

**Screenshot intent**: Parse logs / terminal output for root cause.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| **Installed `systematic-debugging`** | obra ✓ | 45% | Methodology not log parsing |
| [getsentry/skills](https://github.com/getsentry/skills) | partial | 30% | Sentry-specific |
| Generic "log parser" skills | fragmented | 25% | No ≥2-signal canonical repo |

**Recommendation**: Use **`systematic-debugging`** + shell tools; **UNRESOLVED** for dedicated log-parser skill unless user provides URL.

---

## 9. Release Notes (`release-notes`)

**Screenshot intent**: User-facing release notes from git/PRs.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [alibaba/page-agent `update-changelog`](https://github.com/alibaba/page-agent) | SKILL.md ✓ gh integration ✓ | 70% | Changelog + releases |
| [CuriousLearner/devkit `changelog-generator`](https://github.com/CuriousLearner/devkit) | SKILL.md ✓ | 65% | Conventional commits |
| terminalskills.io `changelog-generator` | marketplace | 60% | Third-party registry |

**Recommendation**: `NEED_USER_CONFIRMATION` → install `update-changelog` or `changelog-generator` as single **release-docs** adapter (avoid duplicating both).

---

## 10. Data Cleaner (`data-cleaner`)

**Screenshot intent**: Clean/normalize tabular datasets (CSV/JSON).

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [daymade `docs-cleaner`](https://github.com/daymade/claude-code-skills) | SKILL.md ✓ | 25% | **Documentation** not data |
| panaversity exercise-2.3 | tutorial | 40% | Teaching stub only |

**Recommendation**: **UNRESOLVED** for production upstream — author local skill or point to pandas workflow in project rules.

---

## 11. Screenshot QA (`screenshot-qa`)

**Screenshot intent**: Visual QA from screenshots / static images.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [maxrihter/claude-skill-visual-regression](https://github.com/maxrihter/claude-skill-visual-regression) | README ✓ SKILL.md ✓ workflows ✓ | 75% | Playwright pixel diff |
| [stefan-stepzero/shipkit](https://github.com/stefan-stepzero/shipkit) | shipkit-qa-visual | 60% | Kit bundle |
| [jmagly/aiwg `regression-visual`](https://github.com/jmagly/aiwg) | SKILL.md ✓ | 55% | SDLC framework skill |

**Recommendation**: `NEED_USER_CONFIRMATION` → install `maxrihter/claude-skill-visual-regression` as closest match.

---

## 12. Changelog Miner (`changelog-miner`)

**Screenshot intent**: Extract changes from git history (mining, not writing).

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [CuriousLearner/devkit `changelog-generator`](https://github.com/CuriousLearner/devkit) | ✓ | 65% | Generate + mine commits |
| [alibaba/page-agent `update-changelog`](https://github.com/alibaba/page-agent) | ✓ | 60% | Evidence from git/gh |
| `gh release` / `gh pr list` (no skill) | CLI | 50% | Use user rule `gh` workflow |

**Recommendation**: Merge with **release-notes** decision — one adapter covers both miner + writer.

---

## 13. Dependency Guard (`dependency-guard`)

**Screenshot intent**: Pre-install dependency security scan.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [aptratcn/skill-dependency-guard](https://github.com/aptratcn/skill-dependency-guard) | README ✓ SKILL.md ✓ MIT ✓ | 80% | **ARCHIVED** 2026-04; 0 stars |
| npm/pip audit (no skill) | built-in | 70% | Agent can run without skill |

**Recommendation**: `NEED_USER_CONFIRMATION` — name match is strong but repo archived; safe to copy markdown-only skill or use `npm audit` / `pip audit` in `ci-fixer` routing.

---

## 14. Nightly Runner (`nightly-runner`)

**Screenshot intent**: Scheduled overnight agent tasks.

**Exact-name search**: 0 SKILL.md.

| Candidate | Signals | Overlap | Notes |
|-----------|---------|---------|-------|
| [cursor/plugins `ralph-loop`](https://github.com/cursor/plugins) (installed, hooks enabled) | ✓ | 35% | Interactive loop not cron |
| GitHub Actions `schedule` | platform | 40% | Requires repo workflow auth |
| Cursor Automations | product | 45% | User-level scheduled agents |

**Recommendation**: **UNRESOLVED** as skill — use CI schedule or Cursor Automations with explicit authorization (see `09_AUTOMATION_SAFETY_LIMITS.md`).

---

## Next steps (user decisions)

1. **Batch install candidates** (confirm list): `refactor-legacy-code`, `visual-regression`, `dependency-guard`, `update-changelog` OR `changelog-generator`, optional `legacy-modernizer`.
2. **Provide screenshot source** for: API Stitcher, Prompt Harness, Data Cleaner, Nightly Runner.
3. **Aliases only** (no install): Playwright Scout → `webapp-testing`; Terminal Sense → `systematic-debugging`.
