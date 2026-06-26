# Phase 0 — Repair Baseline (Frozen)

Frozen at repair start on branch `feat/a-share-quant-upgrade-spec` commit `1c1eaa4d1af749cf711452200a32780f0687fa8b`.

## Artifacts

| File | Content |
|------|---------|
| `artifacts/repair_baseline/metrics.json` | 40d backtest: net -2.29%, Sharpe -0.256 |
| `artifacts/repair_baseline/validation.json` | Pre-repair model validation |
| `artifacts/repair_baseline/e2e_failures.json` | `#overview-body` selector missing |
| `artifacts/repair_baseline/build_manifest.json` | Branch, commit, Python version |

## Known baseline deficiencies

- PBO reported as 1.0 on single-strategy matrix
- DSR label ambiguous (scalar without probability)
- `top30_overlap` used as stability but not labeled separately from Rank IC
- Browser E2E failed on `#overview-body`
- Paper engine: instant fill, simplified T+1
- OOS sample ~40 days, negative net return

Do not modify files under `artifacts/repair_baseline/` after upgrade begins.
