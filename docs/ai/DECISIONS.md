# Decisions Log

## 2026-06-16 — Operating System Phase 0

**Decision**: Create branch `chore/cursor-operating-system` from skills audit work.  
**Why**: Desktop spec requires full OS architecture without losing prior audit.  
**Alternatives**: Continue on `chore/cursor-skills-audit` only — rejected; OS scope needs separate deliverable tree.

**Decision**: Preserve `docs/cursor-skills/`; add `docs/cursor-operating-system/`.  
**Why**: Rollback and audit trail for Round 1–2.

**Decision**: Add local markdown-only routers (image-analysis-router, web-content-safety-gate, licensed-media-finder, diagram-architect, mermaid-renderer).  
**Why**: Spec requires unified pipelines; no credential cost; fully reversible.

**Decision**: Subagent definitions in `.cursor/agents/` (chief-orchestrator, security-reviewer, frontend-engineer) as Phase 4 seed.  
**Why**: Documentation-first; expand in Phase 4.

**Decision**: Do not push to remote; no MCP with credentials in Phase 0.  
**Why**: No git remote; hard safety boundary.

## Prior (skills audit)

See `docs/cursor-skills/04_INSTALLATION_DECISIONS.md` for Round 1–2 skill install matrix.
