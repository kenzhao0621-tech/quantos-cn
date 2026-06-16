# China A-Share Quant — Status

**Date**: 2026-06-16 (real-data batch)
**Overall**: `ACTIVE_WITH_LIMITATIONS`
**Trading mode**: `PAPER_TRADING_ONLY` — never auto real-money

## Operating modes

| Mode | Purpose |
|------|---------|
| `FIXTURE` | Deterministic tests only |
| `HISTORICAL` | Completed trading date replay |
| `LATEST_AVAILABLE` | Newest lawful completed/delayed data |
| `LIVE_OR_DELAYED` | When timestamps prove sufficient freshness |

Every report header shows mode, analysis date, provider, freshness, retrieval/market timestamps.

## Capabilities

| Capability | Status |
|------------|--------|
| Four operating modes + mode banners | WORKING |
| AKShare adapter (calendar, indices, spot, bars, sectors) | WORKING (live spot blocked in env) |
| Real universe builder + audit | WORKING |
| Regime v2 from index + breadth | WORKING |
| Sector ranking from industry boards | WORKING (when provider up) |
| Full-universe screening in code | WORKING |
| 100-point scoring v2 + dossiers | WORKING |
| Policy / institutional reports | WORKING (fixture + public template) |
| Backtest (T+1, costs, Sharpe/Sortino) | PRELIMINARY |
| Paper ledger JSONL immutability | WORKING |
| CLI commands (11) + lock files | WORKING |
| Scheduler templates | TEMPLATE ONLY (not enabled) |
| Live full AKShare spot universe | BLOCKED_BY_DATA (network) |

## Tests

- `run-china-quant-tests.py` — 23/23 PASS
- `run-china-quant-full-tests.py` — 15/15 PASS
- `run-china-quant-real-tests.py` — 18 PASS, 2 BLOCKED (live spot)

## Upgrade gate to `VALIDATED_FOR_PAPER_TRADING`

Requires: real full-universe scan, sector ranking, dossiers, latest-available reliability, backtest OOS/walk-forward pass, immutable paper ledger, **≥10 trading-day paper reports**, model monitoring — **not yet met for live data**.

## Backup (this batch)

`.cursor-backups/os-quant-real-20260616-170252/`

Docs: `docs/china-a-share-intelligence/`
