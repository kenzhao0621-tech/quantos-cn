# 03B_LIVE_FRESHNESS_WATCHDOG_REPORT

Generated: 2026-06-16T19:54:57

## checked_at

```json
"2026-06-16T19:54:57"
```

## market_session

```json
"closed"
```

## is_open

```json
false
```

## sentinel_symbols

```json
[
  "600000",
  "000001",
  "300750"
]
```

## checks

```json
[
  {
    "name": "live_spot",
    "passed": false,
    "provider": null,
    "freshness": null
  },
  {
    "name": "index_daily",
    "passed": false,
    "provider": null
  }
]
```

## spot

```json
{
  "dataset": "spot_quotes",
  "success": false,
  "winner": null,
  "attempts": [
    {
      "provider": "rqdata",
      "dataset": "spot_quotes",
      "status": "NOT_CONFIGURED",
      "payload": null,
      "error": "not configured",
      "attempt": 1,
      "elapsed_ms": 0.0,
      "retrieved_at": "",
      "data_hash": "",
      "row_count": 0,
      "freshness": "",
      "limitations": [],
      "endpoint": "",
      "source_dataset": "",
      "run_id": "",
      "market_date": "",
      "is_live": false,
      "is_end_of_day": false,
      "is_manual": false,
      "is_fixture": false
    },
    {
      "provider": "qmt_market_data",
      "dataset": "spot_quotes",
      "status": "NOT_CONFIGURED",
      "payload": null,
      "error": "not configured",
      "attempt": 2,
      "elapsed_ms": 0.0,
      "retrieved_at": "",
      "data_hash": "",
      "row_count": 0,
      "freshness": "",
      "limitations": [],
      "endpoint": "",
      "source_dataset": "",
      "run_id": "",
      "market_date": "",
      "is_live": false,
      "is_end_of_day": false,
      "is_manual": false,
      "is_fixture": false
    },
    {
      "provider": "akshare_sina",
      "dataset": "spot_quotes",
      "status": "FAILED",
      "payload": {
        "row_count": 5527,
        "truncated": true
      },
      "error": "freshness gate: market closed — live freshness cannot be proven (BLOCKED_BY_DATA)",
      "attempt": 3,
      "elapsed_ms": 18896.13,
      "retrieved_at": "2026-06-16T19:55:15",
      "data_hash": "6aa2ac287f5010cb",
      "row_count": 5527,
      "freshness": "END_OF_DAY",
      "limitations": [
        "Sina stock_zh_a_spot; not Eastmoney"
      ],
      "endpoint": "ak.stock_zh_a_spot",
      "source_dataset": "stock_zh_a_spot",
      "run_id": "",
      "market_date": "2026-06-16",
      "is_live": true,
      "is_end_of_day": false,
      "is_manual": false,
      "is_fixture": false
    }
  ],
  "selection_reason": "no provider succeeded",
  "freshness": null,
  "cross_source": null,
  "quarantined": false
}
```

## indices

```json
{
  "dataset": "index_daily",
  "success": false,
  "winner": null,
  "attempts": [
    {
      "provider": "tushare",
      "dataset": "index_daily",
      "status": "EMPTY",
      "payload": null,
      "error": "no index_daily rows",
      "attempt": 1,
      "elapsed_ms": 666.42,
      "retrieved_at": "2026-06-16T19:55:16",
      "data_hash": "",
      "row_count": 0,
      "freshness": "",
      "limitations": [
        "Licensed Tushare API"
      ],
      "endpoint": "",
      "source_dataset": "",
      "run_id": "",
      "market_date": "",
      "is_live": false,
      "is_end_of_day": false,
      "is_manual": false,
      "is_fixture": false
    },
    {
      "provider": "baostock",
      "dataset": "index_daily",
      "status": "SKIPPED",
      "payload": null,
      "error": "unsupported: index_daily",
      "attempt": 2,
      "elapsed_ms": 0.0,
      "retrieved_at": "2026-06-16T19:55:16",
      "data_hash": "",
      "row_count": 0,
      "freshness": "",
      "limitations": [],
      "endpoint": "",
      "source_dataset": "",
      "run_id": "",
      "market_date": "",
      "is_live": false,
      "is_end_of_day": false,
      "is_manual": false,
      "is_fixture": false
    }
  ],
  "selection_reason": "no provider succeeded",
  "freshness": null,
  "cross_source": null,
  "quarantined": false
}
```

## expectation

```json
"latest session close acceptable — no continuous updates required"
```

## verdict

```json
"CLOSED_SESSION"
```
