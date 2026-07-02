# KEEP_FROM_CACHE_WEIGHT_BRANCH

## CacheOS
- `quant/cache_os/` 全套（CacheKey、policy、storage、freshness、invalidation、metrics、registry、prediction_cache）
- `config/cache_policy.yaml`（§3.3 TTL 表，交易/非交易时段切换）
- stale-on-failure fallback（标注而非隐藏）
- cache hit/miss metrics

## ComputeOS
- `quant/compute_os/incremental.py`（upstream fingerprint、params_hash、data_version）
- `quant/compute_os/profiling.py`（step profiler、slow-step logging）

## ScoringOS
- `quant/scoring_os/` 全套
- 固定公式：`Base × Regime × DataQuality − Risk − Execution − Overheat`
- 8 因子权重（§5.4–5.11）
- winsorized percentile normalization
- missing data → neutral 50 + weight halved
- ST/delisting/non-standard audit hard block
- confidence formula（§6.6）
- price-structure-only trade plan（止损/止盈/仓位）

## ExplainOS
- `quant/explain_os/advice_card.py` 四栏解释卡
- `quant/explain_os/language_guard.py` 禁止措辞守卫
- `quant/explain_os/score_breakdown.py` 因子贡献分解

## Advisory Pipeline
- `quant/application/advisory_service.py`（经 v2.3 重写集成 Kronos+Agents+DataTruth）
- `gateway/api/advisory.py`（`/analyze`、`/cache-status`）

## 配置
- `config/score_weights.yaml`

## 前端
- scoring card chips（cache-status、freshness、formula-version）
- 个股弹窗 advisory 渲染

## 测试（85 个，全部保留）
- `tests/cacheos/`（3 文件）
- `tests/computeos/`（1 文件）
- `tests/scoringos/`（2 文件）
- `tests/explainos/`（1 文件）
- `tests/advisory/`（1 文件）

## 文档与示例
- `docs/validation_reports/`（4 份实测报告）
- `docs/user_advisory_examples/`（5000/10000/20000 小资金示例）
- `scripts/generate_v22_reports.py`、`generate_small_account_examples.py`

## 已知 degraded（诚实保留，不得伪造）
- weekday 日历近似（calendar_status=degraded）→ v2.3 用 A 分支真实 trade_calendar 替换
- Kronos/sentiment/money-flow 缺源 → v2.3 用 A 分支 Kronos 真实推理替换
