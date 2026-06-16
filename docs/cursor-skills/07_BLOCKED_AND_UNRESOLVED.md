# Blocked and Unresolved (Updated)

## Round 2 UNRESOLVED (14 screenshot skills)

Refactor Lens, API Stitcher, Migration Buddy, Docs Whisperer, Prompt Harness, Agent Swarm, Playwright Scout, Terminal Sense, Release Notes, Data Cleaner, Screenshot QA, Changelog Miner, Dependency Guard, Nightly Runner

**Deep hunt**: See `10_UPSTREAM_HUNT.md` (2026-06-16).

| Verdict | Count | Skills |
|---------|-------|--------|
| UNRESOLVED (no viable upstream) | 5 | api-stitcher, prompt-harness, data-cleaner, nightly-runner, terminal-sense* |
| NEED_USER_CONFIRMATION (candidates found) | 9 | refactor-lens, migration-buddy, docs-whisperer, agent-swarm, playwright-scout†, release-notes, screenshot-qa, changelog-miner, dependency-guard |

\* `terminal-sense`: use installed `systematic-debugging` as fallback.  
† `playwright-scout`: use installed `webapp-testing` as fallback.

## BLOCKED_BY_CREDENTIAL

| Skill | Notes |
|-------|-------|
| agent-reach | CLI in `.cursor/skill-sources/agent-reach/.venv/bin/agent-reach` (Python 3.11+). `doctor --json` run 2026-06-16 — see channel table below |
| context-pack | Optional MCP; works without for basic briefing |
| last30days | Not installed (Round 1) |
| serper-scrape | Not installed (Round 1) |

## INSTALLED_DISABLED_BY_DEFAULT

| Skill | Enable requires |
|-------|-----------------|
| ralph-loop | Explicit request + max_iterations + stop conditions |

## agent-reach doctor (2026-06-16)

| Channel | Status | User action |
|---------|--------|-------------|
| web, rss, v2ex | ok | None |
| bilibili | ok (search API only) | Optional: `pipx install bilibili-cli` |
| github | warn | `gh auth login` |
| xueqiu | warn | `agent-reach configure --from-browser chrome` after logging in |
| youtube | off | Already in venv via pip; reinstall if needed |
| twitter | off | `pipx install twitter-cli` or OpenCLI |
| reddit, xiaohongshu | off | `agent-reach install --channels opencli` (desktop Chrome session) |
| exa_search | off | `npm i -g mcporter` + Exa MCP URL (API key via mcporter) |
| linkedin, xiaoyuzhou | off | Optional MCP / transcribe install per doctor message |

**CLI**: `/Users/kenzhao/Projects/netlify-demo/.cursor/skill-sources/agent-reach/.venv/bin/agent-reach`

## NEED_USER_CONFIRMATION

- ~~Promote `.cursor/skills/*` → `~/.cursor/skills/` for global use~~ (done 2026-06-16)
- ~~Enable ralph-loop hooks in `.cursor/hooks.json`~~ (done 2026-06-16)
- Install planning-with-files hooks (OthmanAdi includes hook scripts)
- ~~pip install agent-reach~~ (venv editable install; see doctor table)
- pip install: markitdown, context-pack CLI, cartograph CLI
- Batch install upstream hunt candidates (see `10_UPSTREAM_HUNT.md`)

## QUARANTINE (unchanged)

trading-agents — not in screenshot batch; remains QUARANTINE from Round 1
