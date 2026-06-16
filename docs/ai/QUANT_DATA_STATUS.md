# Quant Data Status

**Updated**: 2026-06-16

| Provider | Status | Coverage |
|----------|--------|----------|
| fixture | ACTIVE | Full pipeline deterministic |
| akshare | ACTIVE_WITH_LIMITATIONS | Index + universe metadata + bars when network |
| tushare | BLOCKED_BY_CREDENTIAL | Adapter prepared |
| official exchange | PARTIAL | rules_store references only |

Freshness: see `tools/china_quant/providers/base.py` DataFreshness enum.
