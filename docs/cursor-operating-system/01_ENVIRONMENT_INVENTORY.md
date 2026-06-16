# Environment Inventory (Phase 0)

**Generated**: 2026-06-16  
**Branch**: `chore/cursor-operating-system`

## Runtime

| Component | Detection | Notes |
|-----------|-----------|-------|
| Git root | `/Users/kenzhao/Projects/netlify-demo` | No remote configured |
| Active branch | `chore/cursor-operating-system` | From `chore/cursor-skills-audit` |
| Cursor | v22.22.1 | CLI |
| Node | v22.22.3 | `package.json` present |
| Python | 3.9.6 / 3.11.15 | agent-reach venv uses 3.11 |
| Package manager | npm | `netlify-cli` devDep |
| Container | none | No Dockerfile |
| CI | none in repo | `ci-fixer` skill available |
| Test framework | none configured | Phase 1 gap |

## Cursor configuration

| Path | Exists | Count / contents |
|------|--------|------------------|
| `.cursor/skills/` | yes | 33 skill dirs + routing doc |
| `.cursor/hooks.json` | yes | ralph-loop stop + capture |
| `.cursor/hooks/` | yes | 2 shell scripts |
| `.cursor/mcp.json` | no | — |
| `.cursor/rules/` | no | — |
| `.cursor/agents/` | no → Phase 4 | — |
| `~/.cursor/skills/` | yes | 35 (globalized) |
| `~/.cursor/skills-cursor/` | yes | 18 built-in |
| `~/.cursor/mcp.json` | no | — |
| `~/.cursor/rules/` | no | — |

## Capability inventory

| Capability | Implementation | Scope | Location | Status | Risk | Duplicate With | Recommendation |
|---|---|---|---|---|---|---|---|
| Task planning | planning-with-files | project | `.cursor/skills/planning-with-files` | WORKING | low | superpowers/writing-plans | primary for file-based plans |
| Multi-step workflows | superpowers router | project | `.cursor/skills/superpowers` | WORKING | low | — | primary orchestration |
| Brainstorming | brainstorming (superpowers) | project | `.cursor/skills/brainstorming` | WORKING | low | — | USE_AS_SUBSKILL |
| Writing plans | writing-plans | project | `.cursor/skills/writing-plans` | WORKING | low | planning-with-files | subskill; narrow triggers |
| Context briefing | context-pack | project | `.cursor/skills/context-pack` | WORKING | low | — | primary |
| Repo mapping | repo-cartographer | project | `.cursor/skills/repo-cartographer` | WORKING | low | — | primary |
| Code review | code-review adapter | project | `.cursor/skills/code-review` | WORKING | low | requesting-code-review | adapter only |
| TDD | test-driven-development | project | `.cursor/skills/test-driven-development` | WORKING | low | test-pilot | primary |
| Browser tests | webapp-testing | project | `.cursor/skills/webapp-testing` | WORKING | medium | playwright-scout | primary; scout=alias |
| Debugging | systematic-debugging | project | `.cursor/skills/systematic-debugging` | WORKING | low | debug-radar, terminal-sense | primary |
| Debug adapter | debug-radar | project | `.cursor/skills/debug-radar` | WORKING | low | systematic-debugging | adapter |
| Test adapter | test-pilot | project | `.cursor/skills/test-pilot` | WORKING | low | TDD+webapp | adapter |
| Code cleanup | code-simplifier | project | `.cursor/skills/code-simplifier` | WORKING | low | refactor-lens | primary execute |
| CI repair | ci-fixer | project | `.cursor/skills/ci-fixer` | WORKING | medium | — | primary |
| MCP authoring | mcp-builder | project | `.cursor/skills/mcp-builder` | WORKING | medium | — | primary |
| Frontend impl | frontend-design | project | `.cursor/skills/frontend-design` | WORKING | low | — | primary coding |
| Design research | ui-ux-pro-max | project | `.cursor/skills/ui-ux-pro-max` | WORKING | low | frontend-design | design-only triggers |
| Visual polish | impeccable | project | `.cursor/skills/impeccable` | WORKING | low | — | end-stage only |
| Ship gate | ship-checklist | project | `.cursor/skills/ship-checklist` | WORKING | low | verification-before-completion | adapter |
| Iteration loop | ralph-loop | project | `.cursor/skills/ralph-loop` | INSTALLED_DISABLED_BY_DEFAULT | high | nightly-runner | hooks installed |
| Web/platforms | agent-reach | project | `.cursor/skills/agent-reach` | BLOCKED_BY_CREDENTIAL | medium | serper, last30days | partial doctor ok |
| Documents | markitdown | project | `.cursor/skills/markitdown` | BLOCKED_BY_DEPENDENCY | low | — | pip install pending |
| Skill discovery | find-skills | project | `.cursor/skills/find-skills` | WORKING | low | — | recommend only |
| Humanize text | humanizer | project | `.cursor/skills/humanizer` | WORKING | low | — | primary |
| SSL/certs | certbot-ssl | project | `.cursor/skills/certbot-ssl` | UNVERIFIED | medium | — | smoke test pending |
| PPTX | pptx | project | `.cursor/skills/pptx` | WORKING | low | — | primary |
| Short video | short-video-opening-optimizer | project | `.cursor/skills/short-video-opening-optimizer` | UNVERIFIED | low | — | — |
| Skill authoring | create-skill | built-in | `~/.cursor/skills-cursor/create-skill` | ACTIVE | low | skill-creator | KEEP_EXISTING |
| Meta audit | cursor-skills-audit | user | `~/.cursor/skills/cursor-skills-audit` | WORKING | low | — | user-level |
| Figma MCP | — | — | — | UNVERIFIED | low | — | Phase 1; needs token |
| Mermaid CLI | — | — | — | BLOCKED_BY_DEPENDENCY | low | — | npm install Phase 1 |
| Firecrawl MCP | — | — | — | UNVERIFIED | medium | agent-reach web | Phase 2 |
| Serper / Last30Days | — | — | — | UNRESOLVED | medium | agent-reach | Phase 2 |
| Screenshot QA | — | — | — | UNRESOLVED | medium | webapp-testing | upstream hunt |
| Refactor Lens | — | — | — | UNRESOLVED | medium | code-simplifier | candidate: peizh/refactor-legacy-code |
| Release pipeline | — | — | — | UNRESOLVED | low | — | changelog/release skills |
| Trading agents | — | — | — | QUARANTINE | high | — | not installed |
| Image router | image-analysis-router | project | Phase 1 add | UNVERIFIED | low | — | INSTALL local |
| Web safety gate | web-content-safety-gate | project | Phase 1 add | UNVERIFIED | low | — | INSTALL local |
| Licensed media | licensed-media-finder | project | Phase 1 add | UNVERIFIED | low | — | INSTALL local |
| Academic pipeline | paper-intake etc. | — | — | UNVERIFIED | low | — | Phase 3 local skills |

## Broken / blocked items

| Item | Issue |
|------|-------|
| agent-reach | 4/13 channels ok; twitter/reddit/xhs/exa need setup |
| markitdown | CLI not in PATH |
| mermaid-cli | not installed |
| git remote | none — push blocked |
| gh CLI | not authenticated |

## Missing core capabilities (by layer)

- **C**: Figma MCP, Screenshot QA, visual-regression skill, a11y reviewer
- **D**: Serper, Firecrawl, Last30Days, web safety gate (adding)
- **E**: markitdown CLI, OCR pipeline, image router (adding)
- **F**: paper-intake, Semantic Scholar/Crossref integrations
- **G**: release-notes, changelog-miner, dependency-guard (candidates identified)

## Hooks

| Hook | Script | Purpose |
|------|--------|---------|
| afterAgentResponse | capture-response.sh | Ralph completion promise detection |
| stop | stop-hook.sh | Ralph loop followup (`loop_limit: 20`) |

## Prior audit cross-reference

Round 1–2 details preserved in `docs/cursor-skills/` (not deleted). This OS audit supersedes routing for new work.
