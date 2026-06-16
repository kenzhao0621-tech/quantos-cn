# 05 — Post-Recovery Capability Report

**Date**: 2026-06-16  
**Branch**: `chore/cursor-operating-system`  
**Pre-change commit**: `0dfff67`  
**Backup**: `.cursor-backups/live-provider-tushare-v2-20260616-181432/`

## Executive status

| Field | Value |
|-------|-------|
| Maturity | **ACTIVE_WITH_LIMITATIONS** |
| Non-fixture path | succeeded |
| Selected provider | akshare_sina |
| Market date | 2026-06-16 |
| Freshness | DELAYED (live Sina) |
| Row count | 5527 |
| Quality | passed |

## What works now (demonstrated)

1. **Sina live spot** — `fetch-market-snapshot --live-only` → run `20260616T182312-a29f93a0`, 5527 rows, validate exit 0
2. **Tushare daily spot** — run `20260616T182645-34391f15`, 5513 rows, END_OF_DAY, validate exit 0
3. **Composite routing** — Sina selected first; full 4/4 datasets on run `20260616T182805-39243beb`
4. **Run-bound validation** — no stale manual fallback
5. **Daily analysis** — consumes snapshot by `--run-id` without silent refetch

## Provider matrix

| Provider | Configured | Reachable | Notes |
|----------|------------|-----------|-------|
| akshare_sina | yes | yes | 5527 rows live |
| akshare_eastmoney | yes | no | Remote disconnect |
| tushare | yes | yes | 5513 rows EOD |
| manual_snapshot | yes | yes | Fallback only |

## Why not READY_FOR_10_DAY_PAPER_VALIDATION

- Paper ledger not auto-updated from `quant run-daily`
- Eastmoney still down
- Fewer than 10 real trading-day paper reports
- Multimodal deterministic suite fails without Pillow (pre-existing env gap)

## Verdict

**ACTIVE_WITH_LIMITATIONS** — live non-fixture full-market data now enters composite pipeline, passes DQ, persists with provenance, and drives daily analysis.
