# Test Plan

Per spec §18 — each capability needs structure, dependency, discovery, trigger, functional, security, conflict, rollback tests.

## Phase 0 tests

| Test | Result |
|------|--------|
| Environment inventory | PASS |
| Backup created | PASS |
| Branch created | PASS |
| Skills directory readable | PASS |
| Hooks syntax | PASS (scripts executable) |
| agent-reach doctor | PASS_WITH_LIMITATIONS |

## Phase 1 pending

| Capability | Tests pending |
|------------|---------------|
| image-analysis-router | positive/negative trigger |
| web-content-safety-gate | injection sample |
| mermaid-renderer | render smoke |
| markitdown | CLI functional |

## Integrated scenarios (Phase 5)

A Full-stack app, B UI workflow, C Safe web research, D Paper analysis, E Multi-agent — not run yet
