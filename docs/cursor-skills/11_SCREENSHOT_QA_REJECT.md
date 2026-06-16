# screenshot-qa — REJECTED (audit record)

| Field | Value |
|-------|-------|
| Candidate | maxrihter/claude-skill-visual-regression |
| License | MIT |
| Pinned SKILL SHA | `b95d6a98ae003844f79e176487ee65755216d1be` |
| Decision | **REJECT install** — FALLBACK only |
| PRIMARY | `webapp-testing` |
| Reason | Requires Playwright baseline harness + CI workflows; repo has no `@playwright/test` setup; medium risk from workflow scripts |
| Revisit when | Project adds Playwright visual regression config |

No `.cursor/skills/screenshot-qa/` directory — use `webapp-testing` + `image-analysis-router`.
