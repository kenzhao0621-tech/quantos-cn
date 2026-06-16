# China A-Share Quant — Status

**Date**: 2026-06-16 (batch 3)
**Overall**: `ACTIVE_WITH_LIMITATIONS`
**Trading mode**: `PAPER_TRADING_ONLY`

## End-to-end validation

| Capability | Status |
|------------|--------|
| Trading calendar (fixture) | WORKING |
| Data freshness gate | WORKING — Tests A, stale sample |
| Market regime / NO TRADE | WORKING |
| Sector ranking | WORKING — fixture pipeline |
| Stock screening + scoring | WORKING — fixture pipeline |
| Entry/stop/target/R:R | WORKING |
| Chinese report (3 samples) | WORKING |
| Post-market review | WORKING — sample |
| Live AKShare index | LIMITED — optional `premarket` without fixture |
| Tushare | BLOCKED_BY_CREDENTIAL |
| Backtest auto-run | DISABLED |

## Sample reports (all SAMPLE_FIXTURE)

1. `2026-06-12_PREMARKET.md` — bullish_market (primary candidate)
2. `2026-06-13_PREMARKET.md` — weak_market (NO TRADE)
3. `2026-06-10_PREMARKET.md` — stale_data (refused live entry)
4. `2026-06-12_POSTMARKET.md` — post-market review

Tests: `python3 scripts/run-china-quant-tests.py` — 23/23 PASS
