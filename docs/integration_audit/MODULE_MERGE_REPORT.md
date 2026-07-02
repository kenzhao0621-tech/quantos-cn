# Module Merge Report — v2.3

## Migrated from cache branch (additive)

| Module | Path | Role |
|---|---|---|
| CacheOS | `quant/cache_os/` | L0/L1 cache, TTL, prediction cache |
| ComputeOS | `quant/compute_os/` | Incremental DAG, profiler |
| ScoringOS | `quant/scoring_os/` | Fixed v2.3 formula + penalties |
| ExplainOS | `quant/explain_os/` | 4-panel advice card |
| AdvisoryService | `quant/application/advisory_service.py` | Unified pipeline |
| Advisory API | `gateway/api/advisory.py` | REST endpoints |
| Config | `config/cache_policy.yaml`, `config/score_weights.yaml` | Versioned policies |
| Tests | `tests/{cacheos,computeos,scoringos,explainos,advisory}/` | 85+ unit tests |

## Retained from kronos branch (not overwritten)

| Module | Path | Role |
|---|---|---|
| KronosOS | `quant/models/kronos/` | Sidecar inference + degraded fallback |
| AgentsOS | `gateway/agents/quantos/` | 9-role pipeline, RiskManager veto |
| Validation | `quant/validation/gate.py` | Benchmark gates |
| Research | `quant/research/`, `quant/reports/` | Phase 8 deliverables |
| Backtest | `gateway/backtest/screener_backtest.py` | Real benchmark paths |
| Portal extras | Research reports, risk center, agent cards in portal |

## New in v2.3

| Module | Path | Role |
|---|---|---|
| DataTruthOS | `quant/data_truth_os/` | Provenance contract + gate |
| Source registry | `config/source_registry.yaml` | Domestic source metadata |

## Conflict resolution

- **Scoring formula:** cache branch formula wins; version bumped to `v2.3_integrated_conservative_ashare`
- **Kronos factor:** optional via `include_kronos`; never fabricates; degraded honestly labeled
- **Agents:** optional via `include_agents`; cannot override ScoringOS formula; RiskManager can BLOCK
- **Portal:** kronos UI retained; advisory card merged from cache branch (v2.3 labels)
