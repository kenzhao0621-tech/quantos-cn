# China A-Share Quant Tooling

**Status**: `ACTIVE_WITH_LIMITATIONS` / `PAPER_TRADING_ONLY`

## Setup

```bash
python3 -m venv .venv-china-quant
.venv-china-quant/bin/pip install -r docs/ai/requirements-china-quant-pins.txt
```

Optional: set `TUSHARE_TOKEN` in `.env` (not required; AKShare is primary).

## CLI

```bash
# Fixture (offline, NO TRADE weak market)
.venv-china-quant/bin/python tools/china_quant/cli.py premarket --fixture weak_market

# Live (requires network + trading session; falls back to fixture on error)
.venv-china-quant/bin/python tools/china_quant/cli.py premarket

# Test A — stale data rejection
.venv-china-quant/bin/python tools/china_quant/cli.py test-freshness
```

## Outputs

| Path | Purpose |
|------|---------|
| `docs/ai/daily-trading/YYYY-MM-DD_PREMARKET.md` | Pre-market Chinese report |
| `docs/ai/daily-trading/PERFORMANCE_LEDGER.csv` | Paper-trade / NO TRADE ledger |

## CLI (full intelligence)

```bash
python3 tools/china_quant/cli.py premarket --fixture universe_full
python3 tools/china_quant/cli.py screen --fixture universe_full
python3 tools/china_quant/cli.py stock-dossier --code 601398
python3 tools/china_quant/cli.py backtest --code 601398
python3 tools/china_quant/cli.py paper-trade
python3 tools/china_quant/cli.py validate
python3 tools/china_quant/cli.py test
```

## Architecture

- Providers: `tools/china_quant/providers/`
- Pipeline: `tools/china_quant/intelligence.py`
- Docs: `docs/china-a-share-intelligence/`

## Tests

```bash
python3 scripts/run-china-quant-full-tests.py
python3 scripts/run-china-quant-tests.py
```

## Status

`ACTIVE_WITH_LIMITATIONS` — fixture full-universe validated; live AKShare full scan limited.

See audit: `docs/cursor-operating-system/24_CHINA_QUANT_STATUS.md`
