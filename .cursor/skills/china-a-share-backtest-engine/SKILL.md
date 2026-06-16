---
name: china-a-share-backtest-engine
description: >-
  Backtest A-share strategies with T+1, limits, costs, walk-forward split.
  PAPER_TRADING_ONLY. Use when user requests historical validation.
  tools/china_quant/backtest/
---

# Backtest Engine

```bash
python3 tools/china_quant/cli.py backtest --code 601398
```

Features: T+1, stamp duty, commission, slippage, limit-up/down, walk-forward split.

Validation labels: VALIDATED | PRELIMINARY | UNVALIDATED | FAILED

Do not mark VALIDATED until OOS + walk-forward pass. See `docs/china-a-share-intelligence/12_BACKTEST_ENGINE.md`.
