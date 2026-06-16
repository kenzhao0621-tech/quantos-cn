# Duplication Matrix (Round 1 + Round 2)

## Round 1 pairs (retained)

| Skill A | Skill B | Overlap % | Resolution | Status |
|---------|---------|-----------|------------|--------|
| create-skill | skill-creator | ~85% | KEEP_EXISTING built-in | PASS |
| find-skills | agent-reach | ~20% | Split: discover vs fetch | PASS |

## Semantic pairs (Round 2 — required)

| Skill A | Skill B | Overlap % | Shared triggers | Unique capability | Conflict risk | Action | Primary | Fallback |
|---------|---------|-----------|-----------------|-------------------|---------------|--------|---------|----------|
| Planning with Files | writing-plans | ~35% | multi-step work | persistent state files vs impl plan | medium | stage split | writing-plans | planning-with-files |
| Planning with Files | Context Pack | ~25% | orientation | long-term vs one-shot context | low | stage split | planning-with-files | context-pack |
| Superpowers | brainstorming | ~95% | creative work | bundled sub-skill | high | USE_AS_SUBSKILL | brainstorming | superpowers router |
| Superpowers | writing-plans | ~95% | planning | bundled sub-skill | high | USE_AS_SUBSKILL | writing-plans | superpowers |
| Superpowers | Code Review | ~80% | review PR | requesting-code-review | medium | USE_AS_SUBSKILL | code-review adapter | review-bugbot |
| Superpowers | Debug Radar | ~90% | debug bug | systematic-debugging | high | USE_AS_SUBSKILL | debug-radar adapter | systematic-debugging |
| Test Pilot | Webapp Testing | ~40% | testing | strategy vs e2e exec | medium | stage split | test-pilot adapter | webapp-testing |
| Webapp Testing | Playwright Scout | ~60% | browser | regression vs explore | medium | UNRESOLVED scout | webapp-testing | — |
| Playwright Scout | Screenshot QA | ~45% | visual | explore vs static QA | medium | UNRESOLVED both | webapp-testing | — |
| Code Simplifier | Refactor Lens | ~50% | cleanup | execute vs analyze | medium | UNRESOLVED lens | code-simplifier | — |
| Debug Radar | Terminal Sense | ~35% | logs | method vs log parse | low | UNRESOLVED sense | systematic-debugging | — |
| CI Fixer | Debug Radar | ~30% | failure | CI-only vs general | low | stage split | ci-fixer | systematic-debugging |
| Docs Whisperer | Release Notes | ~40% | docs | dev docs vs user notes | medium | UNRESOLVED | — | markitdown |
| Release Notes | Changelog Miner | ~45% | release | write vs extract | medium | UNRESOLVED | — | — |
| Ship Checklist | Test Pilot | ~25% | ship | gate vs strategy | low | stage split | ship-checklist | verification-before-completion |
| Repo Cartographer | Context Pack | ~35% | repo context | full map vs task pack | low | stage split | repo-cartographer | context-pack |
| Skill Creator | MCP Builder | ~30% | extend agent | SKILL vs MCP server | low | KEEP + split | create-skill | mcp-builder |
| Agent Swarm | Ralph Loop | ~40% | automation | parallel vs loop | high | UNRESOLVED swarm | — | ralph-loop (disabled) |
| Nightly Runner | Ralph Loop | ~35% | scheduled | cron vs loop | high | UNRESOLVED | — | — |
| Dependency Guard | Changelog Miner | ~20% | changes | deps vs commits | low | UNRESOLVED | — | — |
| frontend-design | ui-ux-pro-max | ~70% | UI task | code vs design research | high | stage split | ui-ux-pro-max | frontend-design |
| frontend-design | impeccable | ~50% | UI polish | build vs polish | medium | stage split | frontend-design | impeccable |
| built-in review | code-review | ~60% | code review | bugbot/security vs superpowers | medium | coexist | review-bugbot | code-review |

## Superpowers sub-skills (registered, not duplicated)

brainstorming, writing-plans, executing-plans, subagent-driven-development, test-driven-development, systematic-debugging, requesting-code-review, receiving-code-review, verification-before-completion, using-superpowers
