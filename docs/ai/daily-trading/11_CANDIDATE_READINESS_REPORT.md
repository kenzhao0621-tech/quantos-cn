# 11_CANDIDATE_READINESS_REPORT

Generated: 2026-06-16T19:52:27

## ready

False

## maturity

PIPELINE_VERIFIED_WITH_DATA_GAPS

## gates

```json
[
  {
    "name": "spot_full_market",
    "passed": true,
    "detail": "5527"
  },
  {
    "name": "quality_passed",
    "passed": true
  },
  {
    "name": "non_fixture",
    "passed": true
  },
  {
    "name": "run_id_bound",
    "passed": true
  },
  {
    "name": "major_indices",
    "passed": false,
    "detail": "0 indices persisted"
  },
  {
    "name": "historical_bars",
    "passed": false,
    "detail": "0 partitions; need incremental backfill"
  }
]
```

## rejection_reasons

```json
[
  "major_indices: 0 indices persisted",
  "historical_bars: 0 partitions; need incremental backfill"
]
```
