# CURRENT_ARCHITECTURE — QuantOS 现状架构审计

> 审计日期：2026-07-02 · 分支：`feat/quantos-kronos-agents-refactor` · 基线 commit：`dd14a78`
> 包：`quantos-cn` v4.2.0（Gateway v2.1.0 / Quant v4.0.0）
> 审计方式：静态代码审计 + 数据仓库实测 + 环境探测；证据均附文件路径。

## 1. 技术栈与运行环境

| 项 | 现状 |
|---|---|
| 后端 | FastAPI + Uvicorn（`gateway/api/app.py`），单进程，端口 8787 |
| 数据仓库 | DuckDB（`data/warehouse/quant.duckdb`，视图指向 Parquet 分区） |
| 前端 | 原生 JS 单页应用（`apps/portal-web/`，无构建步骤） |
| 主 venv | `.venv-china-quant` — **Python 3.9.6**，含 akshare 1.16.72 / tushare 1.4.29 / duckdb 1.4.4 / lightgbm 4.6.0 / scikit-learn 1.6.1 / pandas 2.3.3 |
| 硬件 | Apple M3 Pro，18 GB RAM，macOS 15.7 |
| torch | **未安装**（任何 venv 均无） |
| 可用 Python | python3.12 / python3.11（Homebrew）——Kronos 需要 ≥3.10，主 venv 不满足，需 sidecar venv |

## 2. 顶层结构

```
gateway/     FastAPI：API 路由、券商、风控、纸上交易、任务、观测
quant/       量化引擎：providers、warehouse、screener、features、validation、models、portfolio
apps/        portal-web（前端）+ gateway-api（uvicorn 包装）
integrations/ vnpy / qlib 适配层（shim 优先，native 可选）
services/    vnpy_runtime（shim）
scripts/     ~74 个启动/测试/验收/管道脚本
tests/       137 个可收集测试 + executionos/portfolioos/validationos/explainabilityos 子目录
config/      gateway.yaml、agents.yaml、routing_v2.yaml、data_coverage.yaml
configs/     factor_registry.yaml
data/        运行时数据（gitignore），warehouse/historical/parquet/gateway 等
tools/       china_quant 日报管线（含 fixture 模式，与主管线并行）
```

## 3. 数据仓库实测（2026-07-02）

| 表 | 行数 | 日期范围 | 说明 |
|---|---|---|---|
| `daily_bars` | 696,125 | **2025-12-15 ~ 2026-06-26（约 6.5 个月）** | Tushare 日线，未复权 |
| `features` | 661,467 | 2025-12-15 ~ 2026-06-17 | Alpha158 类宽表（KMID/KLEN/ROC5 等） |
| `index_bars` | 1,998 | 2025-02-05 ~ 2026-06-17 | BaoStock/AKShare 指数 |
| `disclosures` | 60 | — | 官方披露 |

**关键限制**：历史深度仅 ~6.5 个月，无法执行重构文档建议的 2016–2021 训练 / 2022–2023 验证 / 2024+ OOS 切分。ValidationOS 必须按真实可用数据自适应窗口，并在所有报告中如实输出日期范围。扩充历史（Tushare/BaoStock 回填 2018+）应列为 Phase 1 任务。

## 4. 分层调用关系

```
portal-web (JS fetch)
  → gateway/api/{app,bff_market,operations,quantos}.py   （envelope 统一响应）
    → quant/application/{screener,market_data,live_market,model_validation}_service.py
      → quant/{warehouse,market_data_fabric,providers/*,features/*,validation/*,models/*}
        → duckdb / akshare / tushare / baostock

gateway/brokers/* ←→ gateway/risk/* ←→ gateway/paper/*   （纸上/影子/工单）
gateway/jobs/manager.py → subprocess: python -m quant <cmd>
integrations/{vnpy,qlib}/* → quant.warehouse（可选 native venv）
```

反向依赖（quant → gateway）仅一处：`quant/screener/screener_report_pdf.py` 引用 `gateway.config.ROOT`。

## 5. 入口

- 网关：`uvicorn gateway.api.app:app --port 8787`（`make app` / `scripts/start-portal.sh`）
- CLI：`python -m quant <command>`（约 30 个命令：update-daily-bars、update-indices、fabric-fetch、build-feature-store、run-daily 等，见 `quant/__main__.py` L586–616）
- 定时：`gateway/monitoring/intraday_background.py` 开市时段每 15 分钟刷新实时行情

## 6. 既有 "OS 层" 模块（上一轮重构遗留，多为真实实现）

| 模块 | 文件 | 真实性 |
|---|---|---|
| ValidationOS 雏形 | `quant/validation/{purged_kfold,walk_forward,rank_ic,overfitting,leakage_detector,calibration,performance}.py` | 真实实现（含 López de Prado 引用、DSR、PBO） |
| ExecutionOS 雏形 | `quant/execution/a_share_rules.py`、`gateway/paper/engine.py` | 真实（T+1、涨跌停、停牌、手数、印花税） |
| PortfolioOS 雏形 | `quant/portfolio/{cost_model,constraints,optimizer,allocator,unified}.py` | 真实（三档成本 profile） |
| FeatureOS 雏形 | `quant/features/{alpha158,factor_library,neutralization,preprocess}.py` | 真实（158 列宽表 + 缓存） |
| ModelOS 雏形 | `quant/models/{lgbm_ranker,ensemble,ml_scorer,baseline}.py` | 真实（LightGBM + Ridge 诚实降级） |
| DataOS 雏形 | `quant/dataos/{quality_checker,drift_detector,corporate_action_checker}.py` | 真实但覆盖不全 |

## 7. 架构主要缺口（对照 QuantOS 2.0 目标）

1. **KronosOS 完全不存在**——仓库无任何 Kronos 代码；且主 venv Python 3.9 与 Kronos 要求（≥3.10）冲突，需独立 `.venv-kronos`（python3.12）+ 子进程 JSON I/O。
2. **AgentsOS 只有启发式雏形**——`gateway/agents/cn_research/workflow.py` 是仓库存在性检查 + 固定置信度，非 9 角色结构化 JSON I/O 多智能体；`/api/v1/agents/invoke` 是 accept-only 桩（`app.py` L220）。
3. **回测 benchmark 是假的**——`gateway/backtest/screener_backtest.py` L135–138：`hs300_proxy = total_ret * 0.6`；事件回测收益硬编码 `[0.01] * len(fills)`。
4. **ResearchOS 缺失**——无参数搜索 / Optuna / ablation。
5. **配置分裂**——`config/` 与 `configs/` 并存；无 `quantos.quick.yaml` 统一研究配置。
6. **双数据管线**——`MarketDataFabric`（带 freshness 门）与 `CompositeMarketDataProvider`（无 freshness 门）并行；`tools/china_quant` fixture 管线与主管线并行。
7. **前端 5 个孤儿页面**（page-reports/agents/native/shadow/risk 有刷新逻辑但无导航入口）；无 K 线/收益曲线图表能力（仅 SVG sparkline）。

## 8. 安全边界（现状已合规，必须保留）

- `PAPER_TRADING_ONLY=True`、`REAL_MONEY_EXECUTION_DISABLED=True` 模块级常量（`gateway/__init__.py` L18、`quant/__init__.py` L8–9）
- 实盘路径仅 CSV 落盘 / 手动确认（`gateway/brokers/live_order.py`：`PENDING_USER_BROKER_CONFIRM`、`USER_MUST_CONFIRM_ON_BROKER`）
- `RiskEngine.evaluate_intent()` 强制 `paper_trading_only`（`gateway/risk/engine.py` L145–146）
- KillSwitch + StateMachine（RESEARCH_ONLY → PAPER → SHADOW → HALTED）
- 前端法律声明 overlay（`index.html` L13–27），全仓无"保证收益/稳赚/必涨"字样
