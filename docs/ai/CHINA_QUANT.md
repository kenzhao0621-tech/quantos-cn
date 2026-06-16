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

## Tests

```bash
python3 scripts/run-china-quant-tests.py
```

## Skills

Primary: `.cursor/skills/china-a-share-daily-trading-outlook/`

See audit: `docs/cursor-operating-system/23_CHINA_A_SHARE_AUDIT.md`

## Safety

- No brokerage connection; user confirms all real orders
- `NO TRADE` is a successful output
- Stale data → not suitable for live entry decisions
