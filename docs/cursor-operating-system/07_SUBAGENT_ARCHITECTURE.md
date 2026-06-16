# Subagent Architecture

## Defined agents (Phase 4 seed)

| Agent | File | Max steps | File ownership |
|-------|------|-----------|----------------|
| Chief Orchestrator | `.cursor/agents/chief-orchestrator.md` | n/a | docs/ai/* task tracking |
| Security Reviewer | `.cursor/agents/security-reviewer.md` | n/a | read-only on code |
| Frontend Engineer | `.cursor/agents/frontend-engineer.md` | n/a | frontend paths |

## Planned (Phase 4)

Product Architect, System Architect, Repository Cartographer, UI UX Designer, Backend Engineer, Database Engineer, Integration Engineer, Test Engineer, DevOps Engineer, Documentation Engineer, Research Agent, Release Manager

## Coordination rules

- Concurrency ≤ 3
- One writer per file
- Separate branches/worktrees for parallel implementation
- Handoff contract required (see chief-orchestrator)
- No self-approved security review

## Cursor Task tool mapping

Use `Task` subagent_type: explore, generalPurpose, shell, bugbot, security-review as appropriate; orchestrator assigns and collects handoffs.
