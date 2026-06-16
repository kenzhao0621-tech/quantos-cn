# Automation Limits

Consolidates `docs/cursor-skills/09_AUTOMATION_SAFETY_LIMITS.md`.

## Ralph Loop

- Hooks: `.cursor/hooks.json`, `loop_limit: 20`
- Skill: `disable-model-invocation: true`
- Required: `max_iterations`, optional `completion_promise`
- Forbidden: auto push, paid API, infinite loop

## Agent Swarm

- Not installed (UNRESOLVED)
- If added: max 3 parallel, single file writer, orchestrator merge

## Nightly Runner

- Not installed
- Allowed tasks only: lint, test, deps review, link check, local reports
- No silent launchd/cron without user confirmation

## Chief Orchestrator

- Max concurrency: 3 subagents
- Handoff contract mandatory
