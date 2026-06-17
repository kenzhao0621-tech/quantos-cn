# Current System Audit (Phase 0)

**Date:** 2026-06-17

## Data
- **Primary store:** DuckDB `data/warehouse/quant.duckdb` — 121 trade dates, 4256-symbol universe
- **Live tier:** akshare/sina snapshot with cache
- **Gaps:** Full index constituent history; minute/tick limited; disclosure PIT partial

## Labels
- T+1 close-to-close with 8+12 bps costs in validation engine
- **Leakage risk:** `pit_passed=True` hardcoded in screener_backtest (flag only, logic uses as_of_date)

## Validation (before upgrade)
- `purged_kfold.py` existed but was **not wired** to production API
- `/api/v1/research/backtest` used event_engine stub

## Paper / Broker
- `paper_store.py` exists; Paper samples mostly `NO_CANDIDATE` blocked records (n=7)
- Broker: browser handoff + Playwright assist; MiniQMT pending on Mac
- Live gates: `REAL_MONEY_DISABLED` enforced in tests

## Screener UI (before)
- Missing PE/PB/disclosure/risk/eligibility on cards

## Strengths
- Multi-factor EOD screener with sector preferences
- Risk engine + kill switch
- Broker connect-flow chain test passing
