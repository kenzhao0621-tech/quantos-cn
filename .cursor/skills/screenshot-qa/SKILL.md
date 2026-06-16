---
name: screenshot-qa
description: >-
  Compare Playwright screenshots against checked-in baselines at standard viewports.
  Use after webapp-testing captures UI. PRIMARY for visual regression; local project
  implementation (not external Screenshot QA candidate). Never auto-update baselines
  on failure — require explicit UPDATE_BASELINES=1.
---

# Screenshot QA (local)

## Commands

```bash
scripts/playwright-baseline.sh    # generate/update baselines
scripts/playwright-compare.sh     # compare only
```

## Viewports

1440×900, 1280×800, 768×1024, 390×844, 360×800

## Baseline location

`tests/visual/baselines/`

## Policy

On visual failure: report diff, save artifacts under `docs/test-output/`, do **not** overwrite baselines without user approval.

See `docs/cursor-operating-system/25_PLAYWRIGHT_VISUAL_QA.md`.
