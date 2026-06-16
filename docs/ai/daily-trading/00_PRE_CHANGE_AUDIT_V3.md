# Pre-Change Audit V3 (V4 batch)

**Date**: 2026-06-16  
**Branch**: `chore/cursor-operating-system`  
**Baseline commit**: `fb84ee6`  
**Backup**: `.cursor-backups/a-share-data-browser-v3-20260616-174342/`

## Current architecture

- `tools/china_quant/` — operating modes, AKShare adapter, daily_runner, universe, scoring, dossiers, backtest, paper ledger
- `quant/` — **new** composite routing, data quality gate, data lake, provider health, acceptance, capability report CLI
- `multimodal/` — **new** image/PDF pipelines, visual QA, MCP, CLI
- `browser/` — **new** Playwright target policy, plugin registry (stealth quarantine), runtime
- `config/` — data coverage, routing, authorized targets

## Existing capabilities (pre-V4)

| Area | Status |
|------|--------|
| FIXTURE daily pipeline | WORKING |
| LATEST_AVAILABLE | BLOCKED_BY_DATA (AKShare spot disconnect) |
| 11 china_quant CLI commands | WORKING |
| Paper ledger JSONL | WORKING |
| Web content safety | 18/18 PASS |
| Playwright visual QA | WORKING |

## Tests at audit time

- `run-china-quant-tests.py` — 23/23 PASS
- `run-china-quant-full-tests.py` — 15/15 PASS
- `run-china-quant-real-tests.py` — 18 PASS, 2 BLOCKED (live spot)
- `run-web-safety-tests.py` — 18/18 PASS
- Secret scan — PASS

## Live-data failures

- `stock_zh_a_spot_em` — RemoteDisconnected
- Full-market path fails; calendar endpoint succeeds

## Gaps addressed in V4

1. Composite multi-provider routing with explicit attempt traces
2. Data coverage matrix + quality gate before analysis
3. Immutable data lake manifests
4. Manual snapshot import path
5. Multimodal provider-neutral tools + MCP
6. Browser target allowlist + stealth quarantine
7. Deterministic test suites separated from LIVE_OPTIONAL

## Minimal patch plan

Extend (not rewrite) `tools/china_quant`; add `quant/`, `multimodal/`, `browser/` packages; config under `config/`.

## Safety

`PAPER_TRADING_ONLY` / `REAL_MONEY_EXECUTION_DISABLED` preserved. No scheduler activation.
