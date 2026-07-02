# BRANCH_DIFF_SUMMARY — QuantOS v2.3 Integration

> 审计日期：2026-07-02  
> 合并基线：`b9591a3`（Phase 0 审计提交，两分支共同祖先）  
> 分支 A：`feat/quantos-kronos-agents-refactor` @ `f5b344e`（10 commits after base）  
> 分支 B：`feat/quantos-cache-weight-formula-refine` @ `fdaaaee`（12 commits after base）  
> 集成分支：`feat/quantos-v23-merge-datatruth-integration`（从 A 拉出）

## 统计

```
124 files changed, 5045 insertions(+), 4551 deletions(-)
```

**关键结论：不能直接 merge B 到 A**——B 在共同祖先之后删除了 A 新增的 Kronos/Agents/Validation/Research/Reports 模块（`quant/models/kronos/`、`gateway/agents/quantos/`、`quant/research/`、`scripts/e2e_quantos_pipeline.py` 等）。必须采用**选择性迁入**策略：以 A 为基座，从 B 迁入 CacheOS/ComputeOS/ScoringOS/ExplainOS/Advisory 新增模块，保留 A 全部 Phase 1–8 成果。

## 分支 A 独有（必须保留）

| 类别 | 路径 |
|---|---|
| KronosOS | `quant/models/kronos/`（sidecar + predictor + data_adapter） |
| AgentsOS | `gateway/agents/quantos/`（9 角色 pipeline + roles + inputs） |
| ValidationOS | `quant/validation/gate.py`、`quant/validation/performance.py`（完整指标） |
| ResearchOS | `quant/research/`（baselines、random search、sensitivity） |
| ReportOS | `quant/reports/`、Phase 8 交付文档 `docs/QUANTOS_*.md` |
| 配置 | `configs/quantos.{quick,standard,strict}.yaml` |
| 脚本 | `scripts/e2e_quantos_pipeline.py`、`run_kronos_smoke.py`、`run_agents_analysis.py`、`run_backtest.py`、`run_research.py`、`setup-kronos-venv.sh` |
| 测试 | `tests/agents/`、`tests/models/test_kronos.py`、`tests/validation/`、`tests/research/`、`tests/reports/`、`tests/features/`、`tests/dataos/` |
| 数据修复 | `quant/version.py`（v7 统一）、`quant/features/market_regime.py` |
| 前端 | 研究报告/风险中心/智能体卡片（Phase 7） |

## 分支 B 独有（必须迁入）

| 类别 | 路径 |
|---|---|
| CacheOS | `quant/cache_os/`（9 文件：CacheKey、TTL policy、L0/L1、PredictionCache、metrics） |
| ComputeOS | `quant/compute_os/`（incremental DAG、profiler） |
| ScoringOS | `quant/scoring_os/`（固定公式、weights、normalization、confidence、trade plan） |
| ExplainOS | `quant/explain_os/`（四栏卡、language guard、score breakdown） |
| Advisory | `quant/application/advisory_service.py`、`gateway/api/advisory.py` |
| 配置 | `config/cache_policy.yaml`、`config/score_weights.yaml` |
| 测试 | `tests/cacheos/`、`tests/computeos/`、`tests/scoringos/`、`tests/explainos/`、`tests/advisory/`（85 个） |
| 前端 | scoring card chips、advisory modal 渲染 |
| 文档 | `docs/refactor_audit/V22_*.md`、`docs/validation_reports/`、`docs/user_advisory_examples/` |

## 两分支都修改（需手工合并）

| 文件 | A 侧变化 | B 侧变化 | 合并策略 |
|---|---|---|---|
| `gateway/api/app.py` | Kronos/Agents 路由、真实 session | advisory router | 保留 A + 挂载 B advisory router |
| `quant/warehouse.py` | adj_factors、daily_bars_adj、trade_calendar | 无额外 | 保留 A |
| `quant/application/screener_service.py` | v7 版本字符串 | 无 | 保留 A |
| `apps/portal-web/*.js` | 研究报告/风险中心 | scoring card | 合并两者 UI |
| `quant/scoring/enrichment.py` | Phase 2 改动 | v2.2 改动 | 保留 A + 接入 ScoringOS |
| `gateway/backtest/screener_backtest.py` | 真实 benchmark | 回退到假 benchmark | **保留 A** |
| `quant/__main__.py` | update-adj-factors 等 | 无 | 保留 A |

## 测试基线

| 分支 | passed | failed | 备注 |
|---|---|---|---|
| A（kronos）@ f5b344e | ~204+ | ~15 pre-existing | Phase 8 e2e 全绿 |
| B（cache）@ fdaaaee | 204 | 17 | +85 新测试全绿，失败为 pre-existing |
