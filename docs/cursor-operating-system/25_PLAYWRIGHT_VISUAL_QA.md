# Playwright Visual QA

## Policy

- **Never** auto-replace baselines after a visual failure.
- Update only via `UPDATE_BASELINES=1 scripts/playwright-baseline.sh` after intentional UI change.
- Failure artifacts: `docs/test-output/playwright-report/`, `docs/test-output/playwright-failures/`

## Viewports

1440×900, 1280×800, 768×1024, 390×844, 360×800

## Fixture

`fixtures/visual-qa/index.html` — frozen timestamp, no animations, no network fonts.

## Workflow

`webapp-testing` → Playwright → `screenshot-qa`

```bash
scripts/playwright-baseline.sh   # first run / intentional update
scripts/playwright-compare.sh    # CI / integration
```
