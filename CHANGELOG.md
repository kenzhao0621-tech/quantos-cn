# Changelog — QuantOS CN

## [2.3.1] — 2026-07-02

### 收盘数据新鲜度 + 选股体验

- **warehouse_eod_service**：选股前检测 DuckDB 是否落后最新交易日，自动 `update-daily-bars` + 仓库 sync
- 选股响应增加 `data_freshness`（仓库截止日、期望收盘日、同步状态）
- 门户 meta chip 展示「数据截止 / 期望收盘 / 实时降级」说明
- 实时模式行情不可用时明确标注「降级为收盘因子」，不再静默展示过时数据
- README 重写：竞品对比（东方财富 / WorkBuddy 类）、Mermaid 逻辑树、优势说明

### 选股修复（2.3.0 后续）

- 移除 live 模式 `LIVE_QUOTES_UNAVAILABLE` 硬拦截，允许 EOD 降级

## [2.3.0] — 2026-07-02

### v2.3 统一集成（feat/quantos-v23-merge-datatruth-integration）

- **DataTruthOS**：国内数据 provenance 契约（`source_url`、`updated_at`、`fetched_at`、`data_version`、`quality_level`）
- **CacheOS / ComputeOS / ScoringOS / ExplainOS**：从 cache 分支选择性迁入，保留 Kronos/Agents 模块
- **Advisory API**：`GET /api/v1/advisory/analyze` + `cache-status`；v2.3 响应信封
- **固定评分公式**：`v2.3_integrated_conservative_ashare`；Agents 不能覆盖公式，RiskManager 可 BLOCK
- **KronosOS**：可选 live 推理 + PredictionCache；降级置信度封顶 0.35
- **门户**：个股弹窗 v2.3 可复现评分卡
- **交付文档**：`docs/integration_audit/` 七份集成报告
- **安全不变**：`PAPER_TRADING_ONLY` / `REAL_MONEY_EXECUTION_DISABLED` 默认关闭实盘

### Kronos / Agents 重构（同分支基线）

- Phase 0–8：数据真实性修复、Kronos sidecar、真实验证基准、九角色 Agents、研究报告门户
- 详见 `docs/refactor_audit/` 与 `docs/delivery/`

## [4.2.0] — 2026-06-26

### 开源发布与文档
- 完整图文并茂 README、跨平台 [docs/INSTALL.md](docs/INSTALL.md)
- [docs/OPEN_SOURCE_MANIFEST.md](docs/OPEN_SOURCE_MANIFEST.md) 开源范围清单
- `scripts/validate-open-source.sh` 推送前隐私扫描
- Windows：`bootstrap.ps1`、`start-app.ps1`、`start-portal.ps1`

### 隐私与路径脱敏
- `quant/paths.py` 跨平台桌面日报目录（`QUANTOS_DESKTOP_REPORTS`）
- 移除源码中硬编码 `/Users/...` 路径
- `.gitignore` 排除运行时账本、审计、memory SQLite

### 实时行情修复
- 休市单次拉取，避免双倍 AKShare 超时
- 门户 live-refresh 超时延长至 300s
- `start-portal.sh` 健康实例复用

### 门户 UX
- 默认管理员；移除角色选择
- 新增「策略验证」页；选股行点击查看详情

## [4.1.0] — 2026-06-26

### 仓库与品牌
- GitHub 仓库正式更名为 **quantos-cn**（原 `netlify-demo`）
- 历史 Netlify 静态演示移至 `legacy/netlify/`
- 全新 README、项目结构文档、GitHub Actions CI

### 实时选股与 Gateway 2.1
- 一键实时智能选股（内置行情刷新）
- 盘中 15 分钟后台自动刷新（`intraday_background`）
- TradingAgents-CN 选股叠加、策略自验证学习循环
- 选股分析 PDF + 日报 PDF 下载修复
- Paper 买卖信号灵敏度提升
- `GET /api/v1/gateway/capabilities`

## [4.1.0] — 2026-06-17

### Phase 1 — 基础设施
- 统一错误 envelope（`user_action`, `retryable`, `details`）
- Paper 启动结构化错误 `PAPER_ENGINE_START_FAILED`
- 前端 RBAC 按钮门控
- 票据 `NO_EXECUTABLE_LINES` 可操作建议
- `/health` 增强

### Phase 2 — 实时数据与选股
- `gateway/market_data_gateway.py` — 数据分级 REALTIME/DELAYED/EOD/STALE
- 选股多样性约束（行业/价格分层）
- 选股 API 返回 `data_tier`, `data_tradeable`

### Phase 3 — 新手流程
- 五步新手配置向导（门户 UI + API）
- `gateway/onboarding/profile.py` — 投资者/风险画像
- 新手一屏报告 API

### Phase 4 — 研究与回测
- `quant/validation/overfitting.py` — DSR, PBO, walk-forward splits
- 回测输出 `overfitting`, `benchmarks`

### Phase 5 — Paper 闭环
- `gateway/paper/engine.py` — 状态机 DRAFT→RUNNING→STOPPED
- Paper 启动/停止联动引擎
- 晋级门控 `promotion_readiness`

### Phase 6 — Broker Gateway
- `gateway/brokers/gateway.py` — Paper/QMT/PTrade sandbox 适配器
- `/api/v1/brokers/gateway/health`

### Phase 7 — 受控实盘门控
- `gateway/live_trading/gates.py` — Level 0–2 默认，`LEGAL_REVIEW_REQUIRED`
- **不启用** `real_money_enabled`（硬编码 false）

### Phase 8 — 开源准备
- 审计文档、迁移计划、测试证据
- README 路线图更新

### 测试
- `tests/test_phase1_infrastructure.py` — 5 cases
- `tests/test_phases_2_8.py` — 11 cases
- Gateway + readiness 回归 PASS
