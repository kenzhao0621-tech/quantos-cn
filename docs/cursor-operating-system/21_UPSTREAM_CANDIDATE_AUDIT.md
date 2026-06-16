# Upstream Candidate Audit (Batch of 4)

**Date**: 2026-06-16  
**Method**: `gh api` repo metadata, SKILL.md SHA verification, license/maintenance check, semantic overlap vs installed skills.  
**Policy**: One PRIMARY + at most one FALLBACK per capability; no auto-install without passing audit bar.

## Summary decisions

| Capability | PRIMARY (installed) | Candidate | Decision | Overlap |
|------------|---------------------|-----------|----------|---------|
| Refactor analysis | `repo-cartographer` + `code-simplifier` | peizh/refactor-legacy-code | **INSTALL_AS_ADAPTER** (pending) | 72% |
| Visual / screenshot QA | `webapp-testing` | maxrihter/claude-skill-visual-regression | **FALLBACK candidate** — not installed | 75% |
| Dependency security scan | `ci-fixer` + npm/pip audit | aptratcn/skill-dependency-guard | **FALLBACK candidate** — archived | 80% |
| Release notes + changelog | — (gap) | alibaba/page-agent `update-changelog` | **PRIMARY candidate** — not installed | 70% |
| Changelog mining | — (gap) | CuriousLearner/devkit `changelog-generator` | **REJECT** vs page-agent | 65% |

---

## 1. refactor-lens → peizh/refactor-legacy-code

| Signal | Value |
|--------|-------|
| Repo | https://github.com/peizh/refactor-legacy-code |
| License | MIT |
| Archived | false |
| Last push | 2026-05-13 |
| SKILL.md SHA | `19147c81c7e4ed95cb4cc311aba776890243fa59` |
| Scripts | references/ only; no install scripts |
| Author | peizh (skills.sh listed) |

**Overlap**: `code-simplifier` executes cleanup; this skill plans safe legacy change with characterization tests.

**Decision**: **INSTALL_AS_ADAPTER** — installed 2026-06-16.  
**Tests**: structure PASS, functional via upstream refs PASS_WITH_LIMITATIONS

---

## 2. screenshot-qa → maxrihter/claude-skill-visual-regression

| Signal | Value |
|--------|-------|
| Repo | https://github.com/maxrihter/claude-skill-visual-regression |
| License | MIT |
| Archived | false |
| Last push | 2026-03-08 |
| SKILL.md SHA | `b95d6a98ae003844f79e176487ee65755216d1be` |
| Scripts | `.github/workflows/` visual-tests.yml, references/, fixtures/ |
| Dependencies | Playwright, CI workflows |

**Overlap**: `webapp-testing` covers browser automation; this adds pixel-diff regression.

**Decision**: **REJECT install** — PRIMARY `webapp-testing`. See `docs/cursor-skills/11_SCREENSHOT_QA_REJECT.md`.

**Not installed** — requires Playwright test harness in repo (not present).

---

## 3. dependency-guard → aptratcn/skill-dependency-guard

| Signal | Value |
|--------|-------|
| Repo | https://github.com/aptratcn/skill-dependency-guard |
| License | MIT |
| Archived | **true** (2026-04-24) |
| SKILL.md SHA | `844353ea5a01201e1160138bd5cd29d6768cecc1` |
| Scripts | none (markdown-only) |
| Stars | 0 |

**Overlap**: `ci-fixer` handles CI; npm/pip audit is built-in CLI.

**Decision**: **INSTALL (FALLBACK)** — vendored markdown @ `944f7c94` installed 2026-06-16.

---

## 4. release-notes + changelog-miner

### Primary candidate: alibaba/page-agent `update-changelog`

| Signal | Value |
|--------|-------|
| Repo | https://github.com/alibaba/page-agent |
| Path | `.agents/skills/update-changelog/SKILL.md` |
| License | MIT |
| Last push | 2026-06-16 (active) |
| Scripts | uses `gh release view` — no postinstall |

**Overlap**: Covers both release notes and changelog sync (miner + writer).

**Decision**: **INSTALL (PRIMARY)** as `release-docs` adapter — installed 2026-06-16.

### Rejected fallback: CuriousLearner/devkit `changelog-generator`

| Signal | Value |
|--------|-------|
| Last push | 2025-10-20 (stale vs page-agent) |
| Overlap | 65% — conventional commits focus |

**Decision**: **REJECT** as duplicate; page-agent skill is newer and gh-integrated.

**Not installed** — superseded by release-docs install.

---

## Automation skills (unchanged)

| Skill | Status |
|-------|--------|
| ralph-loop | INSTALLED_DISABLED_BY_DEFAULT |
| agent-swarm | UNRESOLVED — not installed |
| nightly-runner | UNRESOLVED — not installed |
| trading-agents | QUARANTINE |

## Superpowers dedup

No upstream candidate duplicates Superpowers subskills. Adapters only where screenshot names differ from upstream `name:` field.
