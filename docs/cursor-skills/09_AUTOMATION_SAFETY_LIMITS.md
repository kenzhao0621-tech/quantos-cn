# Automation Safety Limits

Skills in P3 category and loop/swarm automation must follow these limits.

## INSTALLED_DISABLED_BY_DEFAULT

| Skill | Reason | Enable when |
|-------|--------|-------------|
| ralph-loop | Hooks installed in `.cursor/hooks.json`; skill still `disable-model-invocation: true` | User sets max_iterations (default hook `loop_limit`: 20), completion promise, explicit `/ralph-loop` request |

## NOT INSTALLED (P3 — require authorization)

| Skill | Status | Notes |
|-------|--------|-------|
| agent-swarm | UNRESOLVED | No trusted upstream named agent-swarm |
| nightly-runner | UNRESOLVED | No trusted upstream; no system cron without auth |

## Mandatory limits (when enabled)

### Ralph Loop
- `max_iterations` required (recommend ≤ 20)
- `completion_promise` required for exit
- No auto push / deploy / paid API
- Stop hook must not run without user starting loop

### Agent Swarm (if ever installed)
- Max concurrency ≤ 2 by default
- No concurrent edits to same file
- Defined merge owner

### Nightly Runner (if ever installed)
- Dry-run config first
- No system cron without explicit authorization
- Read-only or low-risk tasks only

## agent-reach

- Skill definition installed; execution **BLOCKED_BY_CREDENTIAL**
- Run `agent-reach doctor` only after user provides channel setup
- No cookie/token storage in skill files
