# Installation Decisions (Round 1 + Round 2)

## Round 1 (unchanged outcomes)

See prior rows for find-skills, humanizer, markitdown, certbot-ssl, short-video-opening-optimizer, skill-creator KEEP_EXISTING, agent-reach/last30days/serper deferred.

## Round 2 — Screenshot skills

| Requested | Normalized | Decision | Scope | Notes |
|-----------|------------|----------|-------|-------|
| Planning with Files | planning-with-files | INSTALL | project | OthmanAdi/planning-with-files c020bdd |
| Superpowers | superpowers + subskills | INSTALL + USE_AS_SUBSKILL | project | obra/superpowers 8cf3900 |
| Code Review | code-review | INSTALL_AS_ADAPTER | project | → requesting-code-review |
| Webapp Testing | webapp-testing | INSTALL | project | anthropics/skills |
| Code Simplifier | code-simplifier | INSTALL | project | getsentry/skills |
| MCP Builder | mcp-builder | INSTALL | project | anthropics/skills |
| Ralph Loop | ralph-loop | INSTALL (DISABLED) | project | cursor/plugins; disabled default |
| PPTX | pptx | INSTALL | project | anthropics/skills |
| Context Pack | context-pack | INSTALL | project | Rothschildiuk/context-pack |
| Repo Cartographer | repo-cartographer | INSTALL_AS_ADAPTER | project | anthony-maio/cartograph repo-surveyor |
| Test Pilot | test-pilot | INSTALL_AS_ADAPTER | project | → TDD + webapp-testing |
| Debug Radar | debug-radar | INSTALL_AS_ADAPTER | project | → systematic-debugging |
| Refactor Lens | refactor-lens | UNRESOLVED | — | No trusted upstream |
| API Stitcher | api-stitcher | UNRESOLVED | — | No trusted upstream |
| Migration Buddy | migration-buddy | UNRESOLVED | — | No trusted upstream |
| Docs Whisperer | docs-whisperer | UNRESOLVED | — | 1 low-signal repo |
| Prompt Harness | prompt-harness | UNRESOLVED | — | No trusted upstream |
| Ship Checklist | ship-checklist | INSTALL_AS_ADAPTER | project | → verification-before-completion |
| Agent Swarm | agent-swarm | UNRESOLVED | — | P3 not installed |
| Playwright Scout | playwright-scout | UNRESOLVED | — | Use webapp-testing |
| Terminal Sense | terminal-sense | UNRESOLVED | — | No trusted upstream |
| CI Fixer | ci-fixer | INSTALL | project | cursor/plugins fix-ci |
| Release Notes | release-notes | UNRESOLVED | — | No trusted upstream |
| Data Cleaner | data-cleaner | UNRESOLVED | — | No trusted upstream |
| Screenshot QA | screenshot-qa | UNRESOLVED | — | No single trusted upstream |
| Changelog Miner | changelog-miner | UNRESOLVED | — | No trusted upstream |
| Dependency Guard | dependency-guard | UNRESOLVED | — | 26 repos, none canonical |
| Nightly Runner | nightly-runner | UNRESOLVED | — | P3 not installed |
| UI UX Pro Max | ui-ux-pro-max | INSTALL | project | nextlevelbuilder; triggers narrowed |
| Skill Creator | skill-creator | KEEP_EXISTING | built-in | No second copy |
| impeccable | impeccable | INSTALL | project | pbakaus/impeccable; polish stage |
| agent-reach | agent-reach | INSTALL (BLOCKED exec) | project | Panniantong; creds required |

## Superpowers merge actions

| Previously standalone | Action |
|----------------------|--------|
| brainstorming | MERGE_WITH superpowers — refreshed from upstream, triggers narrowed |
| writing-plans | MERGE_WITH superpowers — refreshed from upstream, triggers narrowed |

No duplicate SKILL.md copied outside `.cursor/skills/<name>/`.
