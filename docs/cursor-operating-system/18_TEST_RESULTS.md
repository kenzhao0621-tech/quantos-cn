# Test Results

**Last run**: 2026-06-16 (batch 2 — local integration)

Run: `scripts/run-local-integration-tests.sh`

| ID | Scenario | Result | Notes |
|----|----------|--------|-------|
| P0-1 | Git branch + backup | PASS | os-audit-20260616-152306 |
| B-1 | Mermaid render | PASS | os-phase.mmd |
| C-1 | web-content-safety-gate fixture | PASS_WITH_LIMITATIONS | injection HTML fixture; manual skill review |
| D-1 | MarkItDown TXT/HTML/DOCX/PPTX/XLSX/PDF | PASS | `.venv-markitdown`, markitdown==0.1.2 |
| E-1 | Subagents count=15 | PASS | `.cursor/agents/` |
| U-1 | refactor-lens adapter | PASS | structure + SOURCE pinned |
| U-2 | release-docs adapter | PASS | vendored SKILL.base.md |
| U-3 | dependency-guard | PASS | markdown vendored, archived upstream |
| U-4 | screenshot-qa candidate | REJECT | webapp-testing PRIMARY |
| R-1 | Research skills (9) | PASS | structure/discovery |
| SEC-1 | Secret scan tracked | PASS | |
| A-1 | Full-stack app scenario | NOT RUN | no backend in demo repo |

**Summary**: PASS=14 FAIL=0 PASS_WITH_LIMITATIONS=1 (automated run)

## China A-share quant (2026-06-16)

Run: `python3 scripts/run-china-quant-tests.py`

| ID | Scenario | Result | Notes |
|----|----------|--------|-------|
| CQ-A | Data freshness stale rejected | PASS | stale_data fixture |
| CQ-B | NO TRADE weak market | PASS | weak_market fixture |
| CQ-C | Entry/stop/target fields | PASS | report template |
| CQ-D | Limit-up blocked | PASS | rules.py |
| CQ-E | Rumor rejected | PASS | news_integrity.py |
| CQ-F | Beginner Chinese report | PASS | |
| CQ-G | Ledger preserves losses | PASS | PERFORMANCE_LEDGER.csv |
| CQ-H | Position guidance | PASS | |
| CQ-I | No forced pick | PASS | |

**Summary**: PASS=12 FAIL=0 — status `ACTIVE_WITH_LIMITATIONS`

Sample report: `docs/ai/daily-trading/2026-06-13_PREMARKET.md`

Prior: `docs/cursor-skills/06_TEST_RESULTS.md`
