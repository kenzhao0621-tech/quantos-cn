---
name: china-quant-data-quality-guard
description: >-
  Verify A-share data freshness, trading calendar, and source timestamps before
  recommendations. Rejects stale data for live decisions. Use with china-a-share-daily-trading-outlook.
  PRIMARY for quant data QA (separate from document-conversion-qa).
---

# China Quant Data Quality Guard

`tools/china_quant/freshness.py` + `tools/china_quant/data.py`

## Status labels

REAL_TIME | DELAYED | PREVIOUS_CLOSE | PARTIAL_DATA | DATA_UNAVAILABLE

If not live-decision OK, state:

**Data is not current enough for a live entry decision.**

## Sources (priority)

1. Official announcements
2. AKShare
3. Tushare (if `TUSHARE_TOKEN` set)
4. Credible news via web-content-safety-gate

Record: source, timestamp, limitations per recommendation.
