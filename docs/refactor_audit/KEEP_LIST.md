# KEEP_LIST — 保留清单

> 状态标注：`KEEP`（原样保留）/ `PATCH`（保留但需修补）。证据见各专项审计文档。

## KEEP — 可靠、真实、有测试，直接保留

| 模块 | 路径 | 理由 |
|---|---|---|
| DuckDB 仓库层 | `quant/warehouse.py` | 视图指向 Parquet 分区，sync manifest 完整 |
| 历史分区存储 | `quant/historical_store.py` | year/month/date 分区 + manifest |
| AKShare 提供方 | `quant/providers/akshare_family.py`、`tools/china_quant/providers/akshare_provider.py` | 实时行情主路径，真实接口 |
| Tushare 提供方 | `quant/providers/tushare_provider.py` | EOD 日线主回填源（有 PATCH 项见下） |
| BaoStock 提供方 | `quant/providers/baostock_provider.py` | 指数回填默认源 |
| 数据编织层 | `quant/market_data_fabric.py` + `config/routing_v2.yaml` | provider 链、freshness/DQ 门、require_live 拒绝 fixture |
| 实时行情服务 | `quant/application/live_market_service.py` | stale_fallback 显式标注 |
| 筛选器核心 | `quant/application/screener_service.py` | 真实多因子（动量/趋势/波动/流动性）+ 中性化 |
| Alpha158 特征 | `quant/features/alpha158.py`、`alpha158_cache.py` | 158 列真实计算 + Parquet 缓存 |
| 中性化 | `quant/features/neutralization.py` | 市值+行业 z-score |
| LGBM ranker | `quant/models/lgbm_ranker.py` | LambdaRank + Ridge 诚实降级（"no silent mock"） |
| ML 门控 | `quant/models/ml_scorer.py` | 门控失败 → baseline_fallback + 明确 degraded 原因 |
| Purged K-Fold | `quant/validation/purged_kfold.py` | 真实 purge/embargo 实现 |
| Walk-forward | `quant/validation/walk_forward.py`、`overfitting.py`（DSR/PBO） | 真实实现 |
| 泄漏检测 | `quant/validation/leakage_detector.py` | 含 survivorship 检查项 |
| 模型验证服务 | `quant/application/model_validation_service.py` | 滚动验证 + 成本/滑点 + 涨跌停 + RankIC/DSR/PBO，落盘 artifacts |
| A 股规则 | `quant/execution/a_share_rules.py`、`quant/tradability/mask.py` | T+1/手数/涨跌停/ST/停牌 |
| 成本模型 | `quant/portfolio/cost_model.py` | research/paper/live 三档佣金+印花税+过户+滑点 |
| 纸上交易引擎 | `gateway/paper/engine.py` | T+1 可卖数量、涨停拒买、停牌拒单、事件溯源 JSONL |
| 风控引擎 | `gateway/risk/engine.py` | kill switch、loss budget、单票/仓位限制、强制 paper_trading_only |
| KillSwitch + 状态机 | `gateway/risk/kill_switch.py`、`gateway/state_machine.py` | 持久化 halt，live 需人工 review |
| 实盘门控 | `gateway/live_trading/gates.py`、`gateway/brokers/live_order.py` | MANUAL_CONFIRM_ONLY，无直连下单 |
| 券商辅助 | `gateway/brokers/{unified_bridge,connection_manager,reconciliation,handoff}.py` | 辅助执行 + 对账，符合产品边界 |
| T+1 证明 | `screener_service.prove_next_day()` | 真实次日验证（收盘对收盘） |
| BFF + envelope | `gateway/api/bff_market.py`、`envelope.py` | 前端契约清晰 |
| 任务管理 | `gateway/jobs/manager.py` | 线程任务 + JSON 持久化 |
| 审计日志 | `gateway/observability/audit.py` | JSONL 审计事件 |
| 前端主体 | `apps/portal-web/{app,api-client,ui-render,viewmodels,action-registry}.js` | 7 个可用页面、免责声明完整、无违禁措辞 |
| CLI | `quant/__main__.py` | ~30 个真实命令 |
| 披露管线 | `quant/disclosures/*`（含 `pit_filter.py`） | PIT 过滤真实 |
| 测试资产 | `tests/`（137 个用例）+ `scripts/run-*-tests.py` | 重构回归基线 |

## PATCH — 保留但必须修补（进入对应 Phase）

| 模块 | 问题 | 修补 Phase |
|---|---|---|
| `quant/providers/tushare_daily_adapter.py` | L51 硬编码 `is_st: False` | Phase 1 |
| `quant/backfill.py` | 无复权因子（adj_factor）管线；历史仅 6.5 个月 | Phase 1 |
| `gateway/market_status.py` | `_live_status()` 不检查 `stale_fallback`，陈旧快照可显示"实时 OK" | Phase 1 |
| `gateway/api/bff_market.py` `sync-all` | 只同步指数+日线，不含 sectors/fundamentals/disclosures | Phase 1 |
| `quant/tradability/mask.py` | 板块差异化涨跌停（科创 20%/北交 30%/ST 5%）未全覆盖，多处扁平 9.8% | Phase 1/4 |
| `gateway/backtest/screener_backtest.py` | benchmark 为假（`total_ret * 0.6`）；无跌停/停牌卖出模拟 | Phase 4 |
| `quant/learning/outcome_tracker.py` | `record_screener_run()` 定义但从未被调用 | Phase 5/6 |
| `quant/screener/alpha_blend.py` | 命名 "alpha158_lite" 实为 5 因子 price_momentum_lite，误导 | Phase 2 |
| `quant/scoring/enrichment.py` | `model_uncertainty` 为启发式公式，非校准不确定度 | Phase 3/4 |
| 模型版本字符串 | v4/v5/v6 三套并存（screener_service / enrichment） | Phase 2 |
| 双注册表 | `artifacts/model_registry.json` vs `memory/MODEL_REGISTRY.json` | Phase 5 |
| 前端孤儿页 | page-reports/agents/native/shadow/risk 无导航 | Phase 7 |
| `gateway/agents/cn_research/*` | 启发式而非结构化多智能体，保留作为 AgentsOS 降级路径 | Phase 6 |
