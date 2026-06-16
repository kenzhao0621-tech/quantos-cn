# Pre-Change Audit — Live Provider + Tushare V2

**Date**: 2026-06-16  
**Branch**: `chore/cursor-operating-system`  
**HEAD**: `0dfff67`

## Root cause (Sina)

- **File**: `quant/providers/akshare_family.py` — class `AkshareSinaProvider` inherits `_AkshareBase.fetch()`
- **Bug**: `spot_quotes` dispatches to `self._provider().get_spot_quotes()` which calls `ak.stock_zh_a_spot_em()` (Eastmoney)
- **Correct endpoint**: `ak.stock_zh_a_spot()` (Sina) — verified 5,527 rows in recovery test

## Sina columns observed (`stock_zh_a_spot`)

`代码`, `名称`, `最新价`, `涨跌额`, `涨跌幅`, `买入`, `卖出`, `昨收`, `今开`, `最高`, `最低`, `成交量`, `成交额`, `时间戳`

## Tushare status

- **Current**: partial stub in `quant/providers/tushare_provider.py` — `daily` + `stock_basic` only
- **Token**: read from `TUSHARE_TOKEN` env; `.env.local` **not** auto-loaded yet
- **User evidence**: trade_cal, stock_basic, daily succeed with valid token

## Snapshot / validation gaps

- Snapshots: **no run_id** in `data_lake.py` manifests
- `validate-latest-snapshot`: resolves by dataset only, falls back to older dates → validated stale `manual_snapshot` (12 rows)
- DQ gate: `min_rows=1` default — too weak for full-market

## Blocks promotion to READY_FOR_10_DAY_PAPER_VALIDATION

1. Sina not wired to composite spot path  
2. Run-bound validation missing  
3. Tushare daily not normalized to spot schema with END_OF_DAY label  
4. Routing prioritizes Eastmoney before Sina  
5. Full daily analysis not bound to persisted non-fixture snapshot  
