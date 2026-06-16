# 16 Automation — CLI & Scheduler

## CLI (paper trading only)

```bash
.venv-china-quant/bin/python tools/china_quant/cli.py premarket [--mode FIXTURE|HISTORICAL|LATEST_AVAILABLE] [--fixture NAME] [--date YYYY-MM-DD]
.venv-china-quant/bin/python tools/china_quant/cli.py latest
.venv-china-quant/bin/python tools/china_quant/cli.py historical --date 2026-06-12
.venv-china-quant/bin/python tools/china_quant/cli.py intraday
.venv-china-quant/bin/python tools/china_quant/cli.py postmarket
.venv-china-quant/bin/python tools/china_quant/cli.py screen
.venv-china-quant/bin/python tools/china_quant/cli.py stock-dossier --code 601398
.venv-china-quant/bin/python tools/china_quant/cli.py backtest --code 601398
.venv-china-quant/bin/python tools/china_quant/cli.py paper-trade
.venv-china-quant/bin/python tools/china_quant/cli.py validate
.venv-china-quant/bin/python tools/china_quant/cli.py test
```

Each command: duplicate-run lock (`.locks/`), structured logs, CST timestamps, preserves prior reports.

## Scheduler

See `docs/ai/daily-trading/SCHEDULER_TEMPLATES.cron` — **not enabled** until manual runs pass.

## Deliverables per run

- `{date}_PREMARKET.md`
- `{date}_UNIVERSE_AUDIT.md` (when universe built)
- `{date}_SECTOR_RANKING.md` (when sectors ranked)
- `{date}_PRIMARY_CANDIDATES/{code}.md`
- `{date}_POLICY_MACRO.md`
- `{date}_INSTITUTIONAL_FLOW.md`
- `{date}_DATA_FRESHNESS.md`
- `{date}_BACKTEST_SUMMARY.md`
- `{date}_RUN_META.json`
