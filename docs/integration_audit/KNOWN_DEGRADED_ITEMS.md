# Known Degraded Items — v2.3

Items honestly labeled; never presented as verified facts.

| Item | Status | Label |
|---|---|---|
| Historical warehouse depth | Partial backfill to 2018 in progress | `data_version` + freshness |
| `adj_factors` Tushare rate limit | Checkpoint resume | degraded on stale adj |
| Kronos sidecar | Optional `.venv-kronos` | `degraded: true`, confidence ≤ 0.35 |
| Sentiment factor | No verified source | neutral 50, weight halved |
| Money-flow factor | No verified realtime source | neutral 50, weight halved |
| Announcement/policy factor | Limited CNINFO integration | partial / missing flagged |
| Northbound realtime | Unavailable per registry | `realtime_northbound_available: false` |
| Agents LLM roles | May use template fallbacks | `degraded` in agents payload on error |

## Safety (not degraded — enforced)

- Paper trading only
- Real money execution disabled
- RiskManager `must_not_trade` → `BLOCKED_BY_RISK` in advisory
