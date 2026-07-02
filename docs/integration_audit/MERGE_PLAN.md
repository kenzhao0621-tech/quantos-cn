# MERGE_PLAN — QuantOS v2.3 合并执行计划

> 分支：`feat/quantos-v23-merge-datatruth-integration`  
> 策略：**以 Kronos/Agents 分支为基座，选择性迁入 Cache/Scoring 模块，新建 DataTruthOS**

## Step 1 — 选择性迁入（git checkout from B）

```bash
git checkout feat/quantos-cache-weight-formula-refine -- \
  quant/cache_os quant/compute_os quant/scoring_os quant/explain_os \
  config/cache_policy.yaml config/score_weights.yaml \
  gateway/api/advisory.py \
  tests/cacheos tests/computeos tests/scoringos tests/explainos tests/advisory \
  scripts/generate_v22_reports.py scripts/generate_small_account_examples.py
```

**不迁入**：B 对 A 文件的删除/回退。

## Step 2 — 新建 DataTruthOS

```
quant/data_truth_os/
├── __init__.py
├── contract.py      # DataTruthRecord dataclass + validation
├── registry.py      # load config/source_registry.yaml
└── validator.py     # gate: source_url/fetched_at/updated_at/data_version/quality_level
config/source_registry.yaml
tests/data_truth_os/
```

## Step 3 — 升级 ScoringOS 至 v2.3

- `SCORE_WEIGHT_VERSION = "v2.3_integrated_conservative_ashare"`
- 权重保持 §5.4 八因子不变
- Kronos 权重 cap ≤ 10%，degraded fallback confidence cap ≤ 0.35

## Step 4 — 重写 AdvisoryService（集成管线）

```
DataOS → DataTruthOS.validate → CacheOS.get_or_compute →
  FeatureOS snapshot → KronosOS.predict (PredictionCache) →
  AgentsOS.run_pipeline → ScoringOS.compose → RiskOS.gate →
  ExplainOS.build_card → AdvisoryOS output
```

## Step 5 — API 统一

- 挂载 `gateway/api/advisory.py` router 到 `app.py`
- 扩展 `/analyze` 参数：`include_agents`、`include_kronos`、`risk_level`
- 返回结构按 §6.3 元数据 envelope

## Step 6 — 前端合并

- 保留 A：研究报告、风险中心、智能体卡片
- 迁入 B：scoring card chips、advisory modal
- 新增：data_truth 来源标注、quality_level 徽章

## Step 7 — 测试

```bash
pytest tests/cacheos tests/computeos tests/scoringos tests/explainos tests/advisory tests/data_truth_os -q
pytest tests/models/test_kronos.py tests/agents/ -q
pytest tests/ -q  # 全量，对比 baseline
```

## Step 8 — 交付文档

生成 `docs/integration_audit/FINAL_INTEGRATION_REPORT.md` 等 7 份报告。

## 提交纪律

```
docs(integration): Phase 0 branch diff audit
feat(cacheos): migrate CacheOS from v2.2 branch
feat(computeos): migrate ComputeOS from v2.2 branch
feat(scoringos): migrate ScoringOS, upgrade to v2.3 formula version
feat(explainos): migrate ExplainOS from v2.2 branch
feat(datatruth): DataTruthOS + source registry
feat(advisory): integrated v2.3 advisory pipeline with Kronos+Agents
feat(portal): merge scoring card + research/risk UI
test(integration): v2.3 integration tests
docs(integration): final integration report
```
