# REFACTOR_PLAN — QuantOS 2.0 重构执行计划

> 分支：`feat/quantos-kronos-agents-refactor`（不改 main）
> 总原则：小步提交；每 Phase 跑测试 + 出报告；任何失败自动降级并标注 `degraded`；默认 paper trading only；不承诺收益。

## 0. 关键环境事实（决定技术路线）

| 事实 | 影响 |
|---|---|
| 主 venv Python 3.9.6，Kronos 需 ≥3.10 | KronosOS 用独立 `.venv-kronos`（python3.12）+ 子进程 JSON I/O（复用 `gateway/native/bridge.py` 模式）；主环境零侵入 |
| M3 Pro / 18GB / 无 GPU CUDA | 按文档策略取 "Apple Silicon" 档：**Kronos-mini 默认，Kronos-small 可选**（torch MPS/CPU 推理）；禁止默认训练 |
| 仓库历史仅 2025-12 起 ~130 交易日 | Phase 1 回填 ≥2018；验证窗口自适应真实数据并如实输出日期范围；窗口不足 → `BLOCKED_BY_VALIDATION: insufficient_history` |
| 大量 OS 层模块已存在且真实 | 策略是 **KEEP/PATCH 优先**，仅 benchmark/事件回测/agent 桩等 REWRITE（见 REMOVE_OR_REWRITE_LIST） |
| 137 个测试可收集 | 作为每 Phase 回归基线 |
| **Phase 0 基线实测：122 passed / 15 failed（2026-07-02，9m44s）** | 15 个失败为重构前既有问题（broker_bridge×2、execution_router×1、phase1_infrastructure×3、phases_2_8×5、screener×2、trading_pipeline×1、含 test_dsr_and_pbo），Phase 1 起逐一分诊；重构目标是不新增失败并逐步清零 |

## Phase 1 — DataOS（修真实性缺口 + 扩历史）

新增/修改（目标目录 `quant/dataos/` 扩展）：

1. `market_status._live_status()` 检查 `stale_fallback`（诚实性 P0）
2. Tushare 适配器修复 `is_st`（name/namechange 推断），补 `paused`/`limit_up`/`limit_down` 派生列
3. 历史回填 ≥2018（`python -m quant update-daily-bars` 分年批量；网络失败 → 保留现窗并标 degraded）
4. `adj_factor` 管线（Tushare adj_factor 接口 → 新 Parquet 分区 + DuckDB 视图）
5. sectors/fundamentals 入仓（`industry_map`、`fundamental` 视图）；`sync-all` 扩展
6. 板块差异化涨跌停表接入 `tradability/mask.py`（主板 10%/ST 5%/科创创业 20%/北交 30%）
7. 交易日历表落仓；fixture 输出改道 `artifacts/test/`
8. 数据质量检查脚本 `scripts/check_data_quality.py --mode quick`

验收：`pytest tests/ -q`（既有基线不回归）+ 新增 `tests/dataos/` + `python scripts/check_data_quality.py --mode quick` 出报告 `artifacts/reports/data_quality_*.json`。

## Phase 2 — FeatureOS（统一命名 + 防未来函数）

1. 统一因子命名：`alpha158_lite` → `price_momentum_lite`（代码+UI+API 字段一次性）；模型版本字符串收敛为单一 `SCREENER_MODEL_VERSION`
2. Alpha158 宽表基于复权价重算（依赖 Phase 1 adj_factor；不可用则标 degraded=unadjusted）
3. 补市场状态特征（指数趋势/波动/成交量 regime）与基本面质量因子（roe/pe/pb 已有 daily_basic 子集）
4. 未来函数检测脚本 `scripts/check_no_lookahead.py`：调用 `quant/validation/leakage_detector.py` 真实跑（替代 run_quantos_audit.py 的合成桩）

验收：`pytest tests/features -q` + `python scripts/check_no_lookahead.py` 通过。

## Phase 3 — KronosOS（全新增）

目录 `quant/models/kronos/`（config/data_adapter/predictor/signal/benchmark/tests）+ sidecar：

1. `scripts/setup-kronos-venv.sh`：python3.12 建 `.venv-kronos`，装 torch + huggingface_hub + Kronos 源码依赖；下载 `NeoQuasar/Kronos-mini` + `Kronos-Tokenizer-2k`（失败 → degraded 记录到 `data/quantos/kronos_status.json`）
2. `kronos_sidecar.py`：sidecar venv 内运行，stdin JSON（symbol、OHLCV lookback、horizon、n_paths）→ stdout JSON（paths、expected_return、volatility、downside_risk、confidence）
3. `KronosSignalProvider`（主 venv）：`predict_distribution()` 调 sidecar；超时/失败 → **统计降级路径**（历史收益 bootstrap Monte Carlo，`degraded: true, reason: ...`）；`generate_signal()` 归一化 score/-1..1 + confidence + risk_penalty + explanation
4. 融合：Kronos 信号作为 `signals.weights` 之一进入筛选器集成层（权重来自 configs/quantos.quick.yaml，可配置；**不单独决定买卖**）
5. `scripts/run_kronos_smoke.py --symbol 000001.SZ --horizon 5 --model mini`

验收：`pytest tests/models/test_kronos.py -q`（含 degraded 路径测试，不依赖网络）+ smoke 脚本出 JSON 报告。

## Phase 4 — ValidationOS（修假 benchmark + 补指标）

1. `screener_backtest.py`：benchmark 换真实 `index_bars` 000300.SH 区间收益；PBO 用真实参数变体；补跌停不可卖/停牌/持仓锁定
2. `event_engine.py` 硬编码收益重写或删除
3. 指标补全（§9.2 清单）：sortino/calmar/downside_dev/tail_loss_95/turnover/avg_holding_days/calibration/parameter_sensitivity/bootstrap_ci/regime_breakdown —— 扩展 `quant/validation/performance.py`
4. 通过门槛（§9.3）实现为 `quant/validation/gate.py`：不满足 → `BLOCKED_BY_VALIDATION`
5. `scripts/run_backtest.py --mode quick --universe csi300 --from <auto>`

验收：`pytest tests/validation -q` + quick 回测出 `artifacts/backtests/` 报告（真实日期范围 + benchmark 对比）。

## Phase 5 — ResearchOS（参数搜索 + 模型对比）

1. `quant/research/`：random search（20–50 trials，快速模式；Optuna 可选依赖，装不上退 random search 并标注）
2. 基线对比矩阵：Buy&Hold、MA crossover、Momentum 20/60、MeanRev、EqualWeight topK、Ridge、LightGBM、Kronos-mini（degraded 时如实标注）
3. 参数敏感性 + ablation 报告；best config / blocked config 落 `artifacts/research/`
4. 接线 `record_screener_run()`；双模型注册表合并（artifacts + memory → 单一 registry）
5. Qlib workflow 假 sharpe 移除

验收：`python scripts/run_research.py --mode quick --trials 30` 出对比报告。

## Phase 6 — AgentsOS（结构化 JSON 多智能体）

`gateway/agents/quantos/`：9 角色（MarketRegime/Technical/Fundamental/Sentiment/Bull/Bear/RiskManager/PortfolioManager/FinalAdvisor）：

1. 输入严格 JSON（§7.2 schema：market_data_summary、kronos_signal、factor_signal、fundamental_summary、news_summary、risk_flags、backtest_evidence、constraints）
2. 输出严格 JSON（§7.3：rating/score/confidence/key_points/risks/evidence_refs/must_not_trade/degraded）
3. 默认引擎：**确定性规则引擎**（读结构化数据出结论，degraded=false 因为不是 mock 而是规则）；LLM 引擎可选接入（无 key → 规则引擎，标注 engine 类型）
4. RiskManager 一票否决 → BLOCKED；FinalAdvisor 输出 A/B/C/D/BLOCKED + 证据 + 失效条件（§7.4 等级语义）
5. 多空辩论：Bull/Bear 各自输出后由 FinalAdvisor 汇总冲突点
6. 替换 `/api/v1/agents/invoke` 桩；`record_screener_run` 学习闭环接入
7. `scripts/run_agents_analysis.py --symbol 000001.SZ --date latest`

验收：`pytest tests/agents -q` + 脚本对 000001.SZ 出全链 JSON。

## Phase 7 — ReportOS / UserOS

1. `quant/reports/`：Markdown 日报/回测报告/参数对比（PDF 复用 reportlab 已有依赖）；全部含免责声明 + degraded 标注段
2. 前端：恢复 page-reports、page-risk 导航；新增 Stock Advisor 评级视图（A/B/C/D/BLOCKED + 多空 + 失效条件）；Portfolio Builder（仓位/行业分布/不可交易原因）；回测收益/回撤曲线（轻量 SVG 图表）；修 app.js 硬编码日期
3. 新手解释块：为什么推荐/基于哪些数据/可能错在哪/失效条件/建议比例上限

验收：`pytest tests/reports -q` + 前端可用性走查（无 npm 构建，走 browser 冒烟）。

## Phase 8 — 端到端验收

1. `scripts/e2e_quantos_pipeline.py --mode quick --paper-only`：数据质量 → 特征 → Kronos smoke → quick 回测 → agents 分析 → 报告生成 串行跑
2. `scripts/generate_final_report.py` → `docs/QUANTOS_KRONOS_REFACTOR_REPORT.md`
3. 交付文档：MODEL_CARD、RISK_DISCLOSURE、BACKTEST_REPORT、DATA_QUALITY_REPORT、AGENT_REPORT
4. 配置：`configs/quantos.quick.yaml`（§15 草案适配）、`quantos.standard.yaml`、`quantos.strict.yaml`
5. 全量 `pytest tests/ -q` + 报告标注每个模块 real/degraded

## 提交纪律

- 每 Phase 至少 1 个 commit（conventional commits：`feat(dataos): ...`）
- Phase 完成条件：验收命令通过 + 报告落盘 + 测试不回归
- 任何外部依赖失败（网络/下载/安装）：记录 degraded 状态文件，流程继续，报告如实标注

## 风险与回退

| 风险 | 缓解 |
|---|---|
| Kronos 模型下载失败（网络墙） | degraded 统计降级路径为一等公民，测试覆盖 |
| 历史回填耗时长/Tushare 限流 | 分年批量 + checkpoint（backfill.py 已有）；先回填 2024+ 保证最小可用窗口 |
| Python 3.9 语法限制 | 主 venv 代码保持 3.9 兼容；3.10+ 语法只出现在 sidecar |
| 既有 137 测试回归 | 每 Phase 前后各跑一次 |
