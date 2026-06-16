# China A-Share Quant — Status

**Date**: 2026-06-16 (full intelligence batch)
**Overall**: `ACTIVE_WITH_LIMITATIONS` → paper ledger qualifies for `VALIDATED_FOR_PAPER_TRADING` (fixture)
**Trading mode**: `PAPER_TRADING_ONLY`

## Capabilities

| Capability | Status |
|------------|--------|
| Provider layer (fixture + AKShare) | WORKING |
| Full-universe fixture (12 stocks) | WORKING |
| Sector rotation + policy + institutional | WORKING |
| Multi-factor scoring v2 | WORKING |
| Stock dossiers | WORKING |
| Backtest (T+1, costs) | PRELIMINARY |
| Paper ledger JSONL (10 days) | WORKING |
| Model monitoring | WORKING |
| Live full AKShare universe scan | LIMITED |

Tests: `run-china-quant-full-tests.py` — 15/15 PASS

Docs: `docs/china-a-share-intelligence/`
