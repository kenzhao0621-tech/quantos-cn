# MODULE_OWNERSHIP_MAP — 合并后模块归属

| OS 层 | 来源分支 | 主路径 | 集成后负责人 |
|---|---|---|---|
| DataOS | A | `quant/warehouse.py`、`quant/backfill.py`、`quant/providers/` | A（保留） |
| DataTruthOS | **新建 v2.3** | `quant/data_truth_os/` | v2.3 新增 |
| CacheOS | B | `quant/cache_os/` | B 迁入 |
| ComputeOS | B | `quant/compute_os/` | B 迁入 |
| FeatureOS | A | `quant/features/`、`quant/screener/alpha_blend.py` | A（保留） |
| KronosOS | A | `quant/models/kronos/` | A（保留） |
| AgentsOS | A | `gateway/agents/quantos/` | A（保留） |
| ScoringOS | B → v2.3 | `quant/scoring_os/` | B 迁入，版本升至 v2.3 |
| ValidationOS | A | `quant/validation/` | A（保留） |
| ResearchOS | A | `quant/research/` | A（保留） |
| RiskOS | A | `gateway/risk/`、`quant/tradability/` | A（保留） |
| AdvisoryOS | B → v2.3 | `quant/application/advisory_service.py` | 重写集成 Kronos+Agents |
| ExplainOS | B | `quant/explain_os/` | B 迁入 + DataTruth 字段 |
| ReportOS | A | `quant/reports/` | A（保留） |
| UserOS | A+B | `apps/portal-web/` | 合并 UI |
| OpsOS | A | `gateway/observability/`、`quant/cache_os/metrics.py` | A+B |

## API 归属

| 端点 | 来源 | v2.3 状态 |
|---|---|---|
| `GET /api/v1/advisory/analyze` | B | **统一主入口** |
| `GET /api/v1/advisory/cache-status` | B | 保留 |
| `GET /api/v1/screener/*` | A | 保留（BFF） |
| `POST /api/v1/models/validate` | A | 保留 |
| `POST /api/v1/research/backtest` | A | 保留（真实 benchmark） |
| Agents invoke | A | 保留，接入 advisory pipeline |
