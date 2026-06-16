# China A-Share Quant — Audit (Phase 1)

**Date**: 2026-06-16  
**Branch**: `chore/cursor-operating-system`

## Existing components (before this batch)

| Component | Status | Notes |
|-----------|--------|-------|
| `trading-agents` (TauricResearch) | **QUARANTINE** | Live trading risk; not installed |
| agent-reach xueqiu | P3 disabled | Cookie/login; not for quant pipeline |
| ui-ux-pro-max charts.csv | OHLC chart guidance only | Not a quant skill |
| research-integrity-guard | ACTIVE | Reused for news/announcement integrity |
| web-content-safety-gate | ACTIVE | Reused for financial news |
| diagram-architect | ACTIVE | Chart generation routing |

**Conclusion**: No duplicate China quant skills. Safe to install new stack.

## New stack (this batch)

| Skill | Role | Overlap |
|-------|------|---------|
| **china-a-share-daily-trading-outlook** | PRIMARY entry | none |
| china-market-rules-engine | A-share rules | none |
| china-quant-data-quality-guard | Freshness + data QA | extends document-conversion-qa patterns |
| china-a-share-quant-research | Research orchestration | agent-reach P1 web only for news |
| china-a-share-factor-lab | Factor/scoring helpers | none |
| china-a-share-backtest-engine | Paper/backtest | PAPER_TRADING_ONLY |
| china-equity-risk-model | Stops, sizing | none |
| china-a-share-event-study | Announcement catalysts | research-integrity-guard |

## Data providers

| Provider | Status | Credential |
|----------|--------|------------|
| AKShare | PRIMARY (free public) | none |
| Tushare | FALLBACK template | `TUSHARE_TOKEN` optional |
| Official announcements | via AKShare + manual URL | none |

## Safety

- **PAPER_TRADING_ONLY** — no brokerage connection
- Real orders: user-only in brokerage UI
- `NO TRADE` is first-class output
- trading-agents remains QUARANTINE

## Tooling

- Venv: `.venv-china-quant/` (gitignored)
- Package: `tools/china_quant/`
- Ledger: `docs/ai/daily-trading/`
- Tests: `scripts/run-china-quant-tests.py`

## Status target

`ACTIVE_WITH_LIMITATIONS` until live AKShare session verified on trading day.
