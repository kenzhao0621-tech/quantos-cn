# 10_BACKTEST_INTEGRITY_REPORT

Generated: 2026-06-16T19:52:27

## checks

```json
[
  {
    "name": "paper_trading_only",
    "passed": true,
    "detail": "True"
  },
  {
    "name": "real_money_disabled",
    "passed": true,
    "detail": "True"
  },
  {
    "name": "pipeline_module_present",
    "passed": true,
    "detail": "/Users/kenzhao/Projects/netlify-demo/tools/china_quant/pipeline.py"
  },
  {
    "name": "historical_store_present",
    "passed": false,
    "detail": "partitioned bars under data/historical"
  }
]
```

## passed

False

## paper_trading_only

True
