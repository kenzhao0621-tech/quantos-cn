# API Contract Report — v2.3 Advisory

## Endpoints

### `GET /api/v1/advisory/analyze`

**Auth:** `X-API-Key` with `market:read`

| Param | Type | Default | Description |
|---|---|---|---|
| `symbol` | string | required | A-share code e.g. `600519.SH` |
| `capital_cny` | float | 10000 | Account capital for position sizing |
| `position_weight` | float | 0.30 | Max position fraction |
| `force_refresh` | bool | false | Bypass cache |
| `include_agents` | bool | true | Run AgentsOS pipeline |
| `include_kronos` | bool | true | Run KronosOS inference |
| `risk_level` | string | medium | `low` / `medium` / `high` |

### `GET /api/v1/advisory/cache-status`

Returns CacheOS metrics, policy session, warehouse data version.

## Response envelope (success)

```json
{
  "ok": true,
  "data": {
    "meta": { "formula_version", "data_version", "cache_status", "compute_time_ms", "generated_at", "symbol" },
    "data_truth": { "verified_count", "degraded_count", "records", "quality_summary" },
    "score": { "...score_breakdown..." },
    "risk": { "penalties", "hard_blocked", "hard_block_reasons" },
    "kronos": { "...optional..." },
    "agents": { "...optional..." },
    "advisory": { "action", "rating", "buy_zone", "stop_loss", "...disclaimer..." },
    "explain": { "...full ExplainOS 4-panel card..." },
    "warnings": ["..."],
    "cache": { "cache_status", "freshness", "..." }
  }
}
```

Portal uses `data.explain` for the scoring card UI.

## Blocked response

`ADVISORY_BLOCKED` when symbol missing data or hard risk block.
