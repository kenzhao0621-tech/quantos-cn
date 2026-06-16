# System Ready Check

**Generated**: 2026-06-16T19:19:28
**run_id**: `20260616T191339-99738834`

## Verdict: `PIPELINE_VERIFIED_WITH_DATA_GAPS`

- Pipeline verified: **True**
- Candidate data ready: **False**
- Spot provider: **akshare_sina** (5527 rows)

## Gates

- [PASS] run_id_match: manifest=20260616T191339-99738834
- [PASS] non_fixture: akshare_sina
- [PASS] row_count: 5527 vs min 5000
- [PASS] valid_symbol_ratio: 1.0000
- [PASS] valid_price_ratio: 0.9982
- [PASS] duplicate_ratio: duplicates=0
- [PASS] provenance_hash: 4263a975664bdb87
- [PASS] market_date_known: 2026-06-16
- [PASS] dataset_spot_quotes: present
- [PASS] dataset_trading_calendar: present
- [PASS] dataset_indices: present
- [FAIL] security_master: not fetched in snapshot
- [FAIL] historical_bars: not persisted — required for per-stock bar-complete gate
- [FAIL] major_indices_coverage: 1/7 benchmarks; have=['sh']
- [FAIL] sector_boards_scale: 12 sector rows
- [PASS] ledger_appended: 2 record(s)
- [PASS] ledger_has_run_id: 20260616T191339-99738834
- [PASS] ledger_has_provider: akshare_sina
- [PASS] ledger_has_freshness: SOURCE_LATEST_TIMESTAMP_UNCONFIRMED