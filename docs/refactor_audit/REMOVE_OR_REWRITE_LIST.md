# REMOVE_OR_REWRITE_LIST — 删除/重写清单

> 状态：`REWRITE`（重写）/ `DEPRECATE`(弃用/隔离) / `UNKNOWN`（真实性无法确认，标 UNVERIFIED）

## REWRITE — 空壳/假数据/占位逻辑，必须重写

| 项 | 路径与证据 | 问题 | 处置 |
|---|---|---|---|
| 回测 benchmark | `gateway/backtest/screener_backtest.py` L135–138 | `hs300_proxy: total_ret * 0.6, equal_weight: * 0.5, buy_hold: * 0.4` —— **伪造的基准对比** | Phase 4 用 `index_bars` 真实沪深300/中证全指收益替换；替换前所有 benchmark 输出标 `UNVERIFIED` |
| 事件回测收益 | `gateway/backtest/event_engine.py` L87 | `rets = [0.01] * len(fills)` 硬编码 1% | Phase 4 重写或删除该引擎 |
| 回测 PBO 变体 | `screener_backtest.py` L133 | PBO 用同一序列反转/子采样构造"变体"，非独立策略 | Phase 4 用真实参数网格变体 |
| Qlib 基线 Sharpe | `integrations/qlib/workflow.py` L33–34 | `sharpe_proxy = 0.5 if scored else 0.0` 硬编码 | Phase 5 用真实回测指标替换或删除 |
| Agent invoke 桩 | `gateway/api/app.py` L220 | 仅返回 `{"status": "accepted"}`，无执行 | Phase 6 接入 AgentsOS 真实编排 |
| 空 trace spans | `gateway/api/app.py` L571 | `{"spans": []}` 恒空 | Phase 8 补齐或删除端点 |
| 空 sectors API | `gateway/api/app.py` L191 | 恒返回 `{"sectors": []}` | Phase 1 接 `data/sectors/*.json` |
| 硬编码 session=CLOSED | `gateway/api/app.py` L156, L587 | 无视真实开闭市状态 | Phase 1 接 `freshness_contract.market_session_status()` |
| 前端硬编码回测日期 | `apps/portal-web/app.js` L113–116 | `as_of_date: "2026-06-16"` 写死 | Phase 7 改为动态最新交易日 |

## DEPRECATE — 弃用、隔离或从路由摘除

| 项 | 路径与证据 | 处置 |
|---|---|---|
| Supermind 提供方 | `quant/providers/supermind_provider.py` L31–36（"integration stub"，恒 SKIPPED） | 从注册表移除或明确标注 NOT_IMPLEMENTED |
| RQData 提供方 | `quant/providers/rqdata_provider.py` L63（恒 SKIPPED "not yet wired"） | 同上，避免虚假能力印象 |
| QMT 行情提供方 | `quant/providers/qmt_provider.py` L43–47（恒 NOT_CONFIGURED） | 保留检测但从默认路由摘除 |
| JQData 局部实现 | `quant/providers/jqdata_provider.py`（仅 security_master） | 标注部分实现 |
| vnpy doctor 恒 OK | `services/vnpy_runtime/main.py` L99：`self._started or True` | 修正为真实状态 |
| vnpy live 网关注册 | `integrations/vnpy/gateway_registry.py` L64–71（XTP/QMT enabled=False 空壳） | 保留 disabled 状态，文档标明是注册占位 |
| GC/MGC 微结构 sidecar | `gateway/sidecar/gc_mgc/`、`app.py` L607 硬编码 `MBP10Snapshot` | 非 A 股范围，隔离为 demo，主流程不引用 |
| `tools/china_quant` fixture 管线 | `fixture_provider.py`、`daily_runner.run_fixture()` | 与主管线物理隔离：fixture 输出禁止进入 `docs/ai/` 面向用户报告，仅限 tests |
| `CompositeMarketDataProvider` | `quant/composite_provider.py`（无 freshness 门的并行数据路径） | 逐步合并进 `MarketDataFabric`，过渡期标注 |
| `schemas/` providers 镜像树 | 与 `quant/providers` 重复 | 收敛为单一来源 |
| 内存态任务表 | `gateway/api/app.py` L64 `_tasks: dict` 不持久化 | 合并进 `gateway/jobs/manager.py` |
| Demo API key | `gateway/config.py` L49、`api-client.js` L7（`demo-local-key-change-in-prod`） | 文档明示本地 demo 性质；GitHub 发布前处理 |

## UNKNOWN / UNVERIFIED — 真实性无法确认

| 项 | 路径 | 说明 |
|---|---|---|
| `models/latest_lgbm_ranker.pkl` | 仓库根 `models/` | 存在但训练数据/指标工件（`artifacts/model_metrics.json`）缺失 → ML 门控判定 degraded；该模型输出在补训练工件前一律 **UNVERIFIED** |
| `artifacts/screener learning cycles` | `artifacts/` | 历史遗留产物，生成过程无法复现者标 UNVERIFIED |
| 泄漏检查桩 | `scripts/run_quantos_audit.py` L103（自述 "Leakage test stub — synthetic"） | 该脚本产生的泄漏结论不可信，Phase 2 用 `quant/validation/leakage_detector.py` 真实跑 |
| `position_monitor` 静默异常 | `gateway/monitoring/position_monitor.py` L24, L39（`except: pass`） | 失败被吞掉，监控结论可能不完整；Phase 1 加日志 |
| `enrichment.py` 预期收益区间 | `quant/explain/bucket_stats.py` | 依赖 `artifacts/score_bucket_stats.json`，缺失时应显示 INSUFFICIENT_HISTORY——需验证 UI 不会展示无来源区间 |
