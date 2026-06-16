# China A-Share Quant — Status

**Date**: 2026-06-16  
**Overall**: `ACTIVE_WITH_LIMITATIONS`  
**Trading mode**: `PAPER_TRADING_ONLY`

## Operational checklist

| Capability | Status | Notes |
|------------|--------|-------|
| Data freshness gate | WORKING | Tests A pass |
| Market regime / NO TRADE | WORKING | Tests B, I pass |
| Chinese report template | WORKING | Test F pass |
| Entry/stop/target fields | WORKING | Test C pass (template) |
| Limit-up block | WORKING | Test D pass |
| Rumor rejection | WORKING | Test E pass |
| Performance ledger | WORKING | Test G pass |
| Position guidance caps | WORKING | Test H pass |
| Live AKShare fetch | LIMITED | Network + market hours; fixture fallback |
| Sector ranking / stock screen | SCAFFOLD | Regime-only; full pipeline TBD |
| Backtest engine | DISABLED | Skill present; no auto-run |
| Intraday scheduler | NOT INSTALLED | Manual / user-request only |
| Notifications | TEMPLATE ONLY | `docs/ai/daily-trading/NOTIFICATION_TEMPLATES.md` |

## Tests A–I

Run: `python3 scripts/run-china-quant-tests.py`

Do not mark `ACTIVE` until live AKShare verified on a trading day and sector/screen pipeline complete.

## Rollback

See `20_ROLLBACK_GUIDE.md` — section "Remove China quant stack".
