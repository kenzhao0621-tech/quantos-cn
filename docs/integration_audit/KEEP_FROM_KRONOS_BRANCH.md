# KEEP_FROM_KRONOS_BRANCH

## 数据层（Phase 1–2）
- ST 真实推断（`tushare_daily_adapter.py` v2，未知=null）
- 板块差异化涨跌停（`tradability/mask.py` board_limit_pct）
- 实时行情过期诚实标注（`market_status.py` stale_fallback 检查）
- DuckDB 视图：industry_map、fundamental、adj_factors、daily_bars_adj、trade_calendar
- 历史日线回填至 2018（~690 万行）
- `quant/version.py` SCREENER_MODEL_VERSION v7
- `scripts/check_no_lookahead.py` 真实泄漏检测

## KronosOS（Phase 3）
- `quant/models/kronos/` 全套（config、data_adapter、predictor、sidecar）
- `.venv-kronos` sidecar 方案（Python 3.12 + torch MPS）
- `scripts/setup-kronos-venv.sh`、`scripts/run_kronos_smoke.py`
- `tests/models/test_kronos.py`

## ValidationOS（Phase 4）
- 真实沪深300/全市场等权 benchmark（删除 total_ret*0.6）
- `quant/validation/gate.py` BLOCKED_BY_VALIDATION
- `quant/validation/performance.py` 完整指标
- `scripts/run_backtest.py`

## ResearchOS（Phase 5）
- `quant/research/` baselines、random search、sensitivity
- `scripts/run_research.py`

## AgentsOS（Phase 6）
- `gateway/agents/quantos/` 9 角色 JSON I/O
- RiskManager 一票否决、FinalAdvisor A/B/C/D/BLOCKED
- `scripts/run_agents_analysis.py`

## ReportOS + UserOS（Phase 7）
- `quant/reports/markdown_report.py`
- 前端：研究报告、风险中心、智能体研究卡片
- `tests/reports/test_phase7_reports.py`

## Phase 8 交付
- `scripts/e2e_quantos_pipeline.py`（全绿）
- `docs/QUANTOS_*.md` 六份交付文档
- `configs/quantos.{quick,standard,strict}.yaml`

## 安全边界
- `PAPER_TRADING_ONLY=true`、`REAL_MONEY_EXECUTION_DISABLED=true`
