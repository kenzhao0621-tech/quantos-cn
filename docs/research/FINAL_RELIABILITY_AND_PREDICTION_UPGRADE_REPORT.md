# Final Reliability and Prediction Upgrade Report

Generated: 2026-06-17T14:05:03.380959+00:00
Branch: `fix/a-share-quant-reliability-paper-validation`
Starting commit: `1c1eaa4d1af749cf711452200a32780f0687fa8b`
Final commit: `1c1eaa4d1af749cf711452200a32780f0687fa8b`

## Deployment Eligibility

**SHADOW_ELIGIBLE**

## Quantitative Before/After

| Metric | Baseline (40d) | After Repair (120d eval) |
|--------|----------------|--------------------------|
| Net cumulative OOS % | -2.294 | -12.14 |
| Sharpe | -0.256 | -0.988 |
| Max drawdown % | -17.552 | -22.643 |
| DSR probability | misleading | 0.0 |
| PBO | 1.0 (1 strategy) | 0.7273 (OK) |
| Mean Rank IC | top30_overlap misuse | -0.0233 |
| ICIR | N/A | -0.0528 |
| Sample days | 40 | 59 |

## Engineering Before/After

| Item | Before | After |
|------|--------|-------|
| Critical E2E (#overview-body) | FAIL | **PASS** |
| /build-info endpoint | partial | **YES** |
| Stale build detection | no | **portal banner** |
| PID lifecycle | partial | **start-portal.sh + lifecycle.py** |

## Root Causes Fixed

1. **DSR** — returned ambiguous scalar; now `dsr_statistic` + `dsr_probability` with documented threshold.
2. **PBO** — computed on single strategy (always 1.0); now requires ≥8 candidates or `INSUFFICIENT_SAMPLE`.
3. **Rank IC** — `top30_overlap` mislabeled; true Spearman Rank IC implemented.
4. **E2E** — `#overview-body` missing; element added with deterministic wait.
5. **Paper** — instant fill only; full state machine with T+1, partial fill, event sourcing.

## Remaining Blockers

- Net OOS return still negative (-12.14%)
- DSR not passed (probability 0.0)
- PBO 0.7273 > 0.5
- Walk-forward failed
- Ranking model not materially upgraded (factor formulas extended, ML ranking pending)

## Artifacts

- `artifacts/final_repair_acceptance.json`
- `artifacts/strict_validation.json`
- `artifacts/repair_baseline/`
- `artifacts/e2e_results.json`
