# 06 — Paper Ledger Integration Report

**Date**: 2026-06-16

## Summary

Daily analysis output from non-fixture `run_id` runs now appends to the append-only paper signal ledger automatically after deliverables are written.

## Implementation

| Component | Path |
|-----------|------|
| Ledger module | `quant/paper_ledger.py` |
| CLI wiring | `quant/__main__.py` (`run-daily`) |
| Signal ledger | `docs/ai/daily-trading/PAPER_SIGNAL_LEDGER.jsonl` |
| CSV mirror | `docs/ai/daily-trading/PERFORMANCE_LEDGER.csv` (append-only) |

## Record fields

Each entry stores: `run_id`, `signal_date`, `market_data_date`, `provider`, `freshness`, `symbol`, `score`, `entry_zone`, `stop`, `target1`, `target2`, `position_size`, `status`, plus `record_type` (`candidate` | `zero_day` | `correction`).

Zero-candidate days use `symbol=NO_CANDIDATE`, `status=zero_candidates`.

## Deterministic tests

`scripts/run-paper-ledger-tests.py` — **5/5 passed**

- candidate-day append
- zero-candidate-day append
- duplicate run rejection
- correction as linked new record
- no mutation of historical records

## Live verification

```bash
python -m quant run-daily --mode latest-available --run-id 20260616T182805-39243beb
```

| Field | Value |
|-------|-------|
| run_id | `20260616T182805-39243beb` |
| record_id | `20260616T182805-39243beb:zero` |
| provider | akshare_sina |
| record_type | zero_day |
| status | zero_candidates |

Re-run correctly reports `skipped_duplicate: true` without modifying the existing record.

**Status**: INTEGRATED
