# Installation Decisions

Extends `docs/cursor-skills/04_INSTALLATION_DECISIONS.md`.

## Phase 0 — no new upstream installs

Audit + backup + branch only.

## Phase 1 — local installs (this branch)

| Component | Decision | Notes |
|-----------|----------|-------|
| image-analysis-router | INSTALL | local SKILL.md |
| web-content-safety-gate | INSTALL | local SKILL.md |
| licensed-media-finder | INSTALL | local + ledger |
| diagram-architect | INSTALL | local |
| mermaid-renderer | INSTALL | BLOCKED until CLI in package.json |
| @mermaid-js/mermaid-cli | INSTALL | devDependency |
| chief-orchestrator | INSTALL | `.cursor/agents/` |
| security-reviewer | INSTALL | agent def |
| frontend-engineer | INSTALL | agent def |

## Unchanged from prior audit

See prior table for 33 project skills. 14 screenshot names remain UNRESOLVED — `docs/cursor-skills/10_UPSTREAM_HUNT.md`.

## Rejected / quarantined

| Name | Decision |
|------|----------|
| trading-agents | QUARANTINE |
| agent-swarm | UNRESOLVED — high risk |
| nightly-runner | UNRESOLVED — no OS cron without auth |
