# A-Share Quant Platform Upgrade — Final Report

**Date:** 2026-06-17  
**Branch:** `feat/a-share-quant-upgrade-spec`  
**Specification:** `docs/research/A_SHARE_QUANT_UPGRADE_SPEC.md`

## Deployment Eligibility: SHADOW_ELIGIBLE

---

## 1. Branch name and commit hash

- **Branch:** `feat/a-share-quant-upgrade-spec`
- **Pre-upgrade commit:** `e68ed043d32de43298843d3fc2ca3787f868974e`
- **Post-upgrade commit:** see `git rev-parse HEAD` after commit

## 2. Backup location

`artifacts/rollback_20260617_212826/` (+ git stash `pre-quant-upgrade-stash`)

## 3–8. Research

- **Search date:** 2026-06-17
- **Databases:** arXiv, RePEc, Springer, MDPI, O'Reilly, PyPI
- **Sources reviewed:** 8 | **Full-text read:** 2
- **Newest year:** 2026

## 9–15. Findings & methods

**Adopted:** Purged K-fold gating, walk-forward, DSR/PBO, tradability mask, multi-target enrichment, 5000 CNY allocator, diversity constraints, screener backtest API routing.

**Rejected:** Deep learning / GNN / self-attention rankers — no stable net-of-cost OOS beat vs simple baseline; weak A-share execution realism in literature.

## 16–24. Code changes

See `artifacts/experiment_registry.json` and git diff on branch.

## 25–34. Quantitative results

From `artifacts/baseline_system_manifest.json`:

| Metric | Value |
|--------|-------|
| Net OOS daily return (9d) | +0.299% |
| 40d backtest total return | -2.294% |
| Max drawdown (40d) | -17.55% |
| Sharpe (40d) | -0.256 |
| DSR (30d val) | 6.59 (passed) |
| PBO | 1.0 (failed) |
| Purged K-fold | passed |
| Walk-forward | passed |
| Turnover | daily rebalance, sector cap 2 |
| Costs | 8 bps + 12 bps slippage |

## 35–39. Tests

- Unit (quant upgrade): 6/6 pass
- Broker dry-run: pass
- API enrichment: pass after gateway restart
- Browser E2E: FAIL (`#overview-body` timeout)
- Pre-existing failures: onboarding API 404, affordability_budget import

## 40–43. Blockers & owner actions

1. Paper samples < 20 — continue Paper runs
2. Fix portal overview E2E
3. MiniQMT unavailable on Mac — browser handoff only
4. Do not enable unattended live trading
5. Restart gateway after deploy
