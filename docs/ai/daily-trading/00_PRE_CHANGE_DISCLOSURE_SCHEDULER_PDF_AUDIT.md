# Pre-Change Disclosure / Scheduler / PDF Audit

Generated: 2026-06-16

## Findings

- **Why disclosures = 0**: `quant/backfill.update_disclosures` used Tushare `anns` which returned empty; no official SSE/SZSE/BSE/CNINFO path existed.
- **Provider status**: Third-party only (Tushare), not distinguished from verified zero-result official query.
- **Candidate gate**: Required `total_rows >= 50` in `quant/candidate_data_gate.py` — incorrect for official zero-announcement windows.
- **Scheduler**: Forward-looking BaoStock calendar fix present in `quant/live_test_scheduler.py` but not fully exposed via CLI until this batch.
- **PDF**: Daily report was Markdown/JSON only; no Desktop PDF delivery.
- **Backup**: `.cursor-backups/disclosure-scheduler-pdf-20260616-210637`
