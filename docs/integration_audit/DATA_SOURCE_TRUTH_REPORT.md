# Data Source Truth Report — v2.3

All domestic data entering advisory must pass **DataTruthOS** with:

`source_url`, `updated_at`, `fetched_at`, `data_version`, `quality_level`

## Registry (`config/source_registry.yaml`)

| Source ID | Tier | URL | Notes |
|---|---|---|---|
| `sse_official` | S | https://www.sse.com.cn | Exchange disclosure |
| `szse_official` | S | https://www.szse.cn | Exchange disclosure |
| `cninfo` | S | http://www.cninfo.com.cn | Announcements |
| `tushare_pro` | A | https://tushare.pro | EOD bars, fundamentals |
| `akshare` | A | https://akshare.akfamily.xyz | Auxiliary vendor |
| `baostock` | A | http://baostock.com | Historical fallback |
| `kronos_mini` | A (degraded→C) | https://huggingface.co/NeoQuasar/Kronos-mini | Model forecast only |

## Explicitly unavailable / degraded

- **Northbound realtime:** `realtime_northbound_available: false` — no fabricated intraday northbound flow
- **Sentiment / money-flow / policy:** no verified feed → neutral score 50, weight halved, flagged missing
- **Kronos:** real sidecar when `.venv-kronos` available; else bootstrap MC fallback with `degraded: true`, confidence capped ≤ 0.35

## DataTruthOS gate

`gate_for_advisory()` in advisory envelope reports `verified_count`, `degraded_count`, per-record provenance.

## Warehouse

Primary store: `data/warehouse/quant.duckdb` (Tushare-sourced EOD). `warehouse_data_version()` keys CacheOS invalidation.
