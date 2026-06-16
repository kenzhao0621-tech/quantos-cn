# Test Results

**Last run**: 2026-06-16 (batch 3 — full validation)

Run: `scripts/run-local-integration-tests.sh`

| ID | Scenario | Result | Notes |
|----|----------|--------|-------|
| A-1 | Full-stack Scenario A | PASS | unit=PASS e2e=PASS |
| B-1 | Mermaid render | PASS | os-phase.mmd |
| C-1 | web-content-safety-gate | PASS | scripts/run-web-safety-tests.py |
| D-1 | MarkItDown | PASS | .venv-markitdown |
| E-1 | Subagents count>=15 | PASS | count=15 |
| F-1 | Playwright visual baselines | PASS | 5 viewports |
| CQ-1 | A-share tests A–I + M6 | PASS | run-china-quant-tests.py |
| CQ-2 | A-share bullish fixture report | PASS | SAMPLE_FIXTURE |
| CQ-3 | A-share NO TRADE weak | PASS | weak_market |
| CQ-4 | A-share stale refusal | PASS | stale_data |
| SEC-1 | Secret scan tracked | PASS | |
| SK-screenshot-qa | Skill screenshot-qa | PASS | |
| SK-web-content-safety-gate | Skill web-content-safety-gate | PASS | |
| SK-china-a-share-daily-trading-outlook | Skill china-a-share-daily-trading-outlook | PASS | |

**Summary**: PASS=14 FAIL=0 PASS_WITH_LIMITATIONS=0
