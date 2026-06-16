---
name: china-a-share-backtest-engine
description: >-
  Backtest and paper-trade A-share strategies with costs, suspensions, and price limits.
  PAPER_TRADING_ONLY — INSTALLED_DISABLED_BY_DEFAULT for live signals. Use only when
  user requests historical validation. Never describe backtest as guaranteed future performance.
disable-model-invocation: true
---

# Backtest Engine

**Status**: PAPER_TRADING_ONLY — scaffold; full backtest not yet implemented.

## Requirements when implemented

- Transaction costs
- Suspensions & limit up/down
- No survivorship bias / no future leakage
- Benchmark comparison

## Current

Use `PERFORMANCE_LEDGER.csv` for forward paper tracking.

Do not auto-run backtests without user request.
