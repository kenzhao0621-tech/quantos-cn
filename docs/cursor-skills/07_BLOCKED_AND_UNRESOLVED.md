# Blocked and Unresolved (Updated)

## Round 2 UNRESOLVED (14 screenshot skills)

Refactor Lens, API Stitcher, Migration Buddy, Docs Whisperer, Prompt Harness, Agent Swarm, Playwright Scout, Terminal Sense, Release Notes, Data Cleaner, Screenshot QA, Changelog Miner, Dependency Guard, Nightly Runner

**Reason**: No single upstream with ≥2 verification signals (README + SKILL.md + license + recent commits) matching the screenshot name.

## BLOCKED_BY_CREDENTIAL

| Skill | Notes |
|-------|-------|
| agent-reach | CLI + channel tokens; definition installed |
| context-pack | Optional MCP; works without for basic briefing |
| last30days | Not installed (Round 1) |
| serper-scrape | Not installed (Round 1) |

## INSTALLED_DISABLED_BY_DEFAULT

| Skill | Enable requires |
|-------|-----------------|
| ralph-loop | Explicit request + max_iterations + stop conditions |

## NEED_USER_CONFIRMATION

- Promote `.cursor/skills/*` → `~/.cursor/skills/` for global use
- Enable ralph-loop hooks in `.cursor/hooks.json`
- Install planning-with-files hooks (OthmanAdi includes hook scripts)
- pip install: markitdown, context-pack CLI, cartograph CLI, agent-reach

## QUARANTINE (unchanged)

trading-agents — not in screenshot batch; remains QUARANTINE from Round 1
