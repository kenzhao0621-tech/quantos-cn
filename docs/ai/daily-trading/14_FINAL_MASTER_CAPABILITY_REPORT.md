# 14_FINAL_MASTER_CAPABILITY_REPORT

Generated: 2026-06-16T19:52:27

## pre_change_commit

07af470cb51f91dd45fa9e220297d2d9e4b62cca

## branch

chore/cursor-operating-system

## run_id

20260616T195313-a542f760

## session_open

False

## require_live_used

False

## live_blocked_reason

market closed

## spot_provider

akshare_sina

## row_count

5527

## data_date

2026-06-16

## tests

```json
{
  "multiprovider_v2": true,
  "provider_recovery": true,
  "paper_ledger": true,
  "next_session": true,
  "v4_deterministic": true
}
```

## maturity

PIPELINE_VERIFIED_WITH_DATA_GAPS

## decision

BLOCKED_BY_DATA

## paper_trading_only

True

## real_money_execution_disabled

True

## feature_store

```json
{
  "historical_partitions": 0,
  "trade_dates": [],
  "feature_modules": [
    "momentum_20d",
    "volatility_20d",
    "liquidity_rank"
  ],
  "status": "partial",
  "point_in_time": "bars keyed by trade_date partition; no intraday mixing"
}
```

## backup

.cursor-backups/quant-master-readiness-20260616-193503
