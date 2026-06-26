# FUNCTION_REALITY_MATRIX

> 生成时间：2026-06-17  
> 审计范围：QuantOS CN 全仓库（Gateway + Portal + quant + brokers）  
> 分类：KEEP / REBUILD / HIDE / REMOVE / EXPERIMENTAL

| 功能 | 页面 | API | 数据源 | 是否真实可用 | 是否有测试 | 是否有用户价值 | 风险 | 处理 |
|---|---|---|---|---|---|---|---|---|
| 门户登录 | 登录遮罩 | `POST /api/v1/auth/login` | `config/gateway.yaml` keys | ✅ 可用 | ✅ E2E | ✅ 高 | 开发密钥硬编码 | KEEP（Phase6 换正式认证） |
| Paper 启动 | 总览/Paper | `POST /api/v1/paper/start` | 状态机+runtime_state | ⚠️ admin/researcher 可用；viewer 403 | ✅ Phase1+验收 | ✅ 高 | UI 未门控（Phase1 已修） | REBUILD→KEEP |
| Paper 持仓/订单 | Paper | `GET /api/v1/paper/*` | `paper_store.json` | ✅ 只读可用 | ✅ gateway-test | ✅ 高 | 非真实引擎，仅状态切换 | KEEP（标注限制） |
| Shadow 模拟 | Paper/总览 | `POST /api/v1/shadow/*` | shadow adapter | ⚠️ 需 mode:promote | ✅ 验收 | ✅ 中 | 同 Paper 权限问题 | REBUILD |
| 智能选股 EOD | 选股 | `GET /api/v1/screener/run` | DuckDB daily_bars | ✅ 可用（有仓库时） | ✅ screener_backtest | ✅ 高 | 缺 walk-forward | KEEP |
| 智能选股 Live | 选股 | mode=live/live_cached | live_snapshot.json | ⚠️ provider 需配置 | ⚠️ 部分 | ✅ 高 | 延迟标实时 | KEEP（标注 tier） |
| 价格/预算筛选 | 选股偏好 | preferences + screener | user_preferences.json | ✅ 服务端过滤 | ⚠️ 无专测 | ✅ 高 | 默认流动性门槛极高 | KEEP |
| 订单票据 EOD | 选股/Autopilot | `POST /api/v1/autopilot/order-ticket` | screener+eod | ✅ 可用 | ✅ Phase1 | ✅ 高 | 空行 UX 混淆 | REBUILD→KEEP |
| 订单票据 Live | 同上 | mode=live | live_cached | ⚠️ 高价股+小资金空行 | ✅ Phase1 | ✅ 中 | 资金约束 | KEEP |
| 券商连接向导 | 券商 | `GET/POST /api/v1/brokers/*` | broker_config.json | ⚠️ 探测/手递 | ❌ 无专测 | ✅ 高 | 无真实 API | EXPERIMENTAL |
| 成交对账 | 券商 | `POST /api/v1/brokers/reconcile` | CSV import | ⚠️ 需用户 CSV | ❌ | ✅ 中 | 手工流程 | KEEP |
| 实时行情刷新 | 市场 | `POST /api/v1/market/live/refresh` | MarketDataFabric | ❌ 全部 NOT_CONFIGURED | ⚠️ | ✅ 高 | 延迟标实时 | HIDE→Phase2 |
| 数据同步 | 市场/总览 | `POST /api/v1/market/sync-all` | Tushare/akshare | ⚠️ 需 Token | ✅ 部分 | ✅ 高 | 网络依赖 | KEEP |
| 回测 | 研究 | `POST /api/v1/research/backtest` | screener_backtest | ⚠️ 慢；无 PBO | ⚠️ | ✅ 高 | 过拟合风险 | REBUILD Phase4 |
| 日报生成 | 报告 | `POST /api/v1/research/daily-run` | china_quant pipeline | ✅ 可用 | ✅ daily | ✅ 高 | fixture 模式混用 | KEEP |
| 风控熔断 | 总览 | `POST /api/v1/risk/halt` | kill_switch.json | ✅ 可用 | ✅ gateway-test | ✅ 高 | — | KEEP |
| 多智能体研究 | 研究 | `POST /api/v1/research/agents/run` | gateway/agents | ⚠️ 确定性本地 | ✅ 部分 | ⚠️ 中 | 非交易指令 | EXPERIMENTAL |
| vn.py 原生 | 原生 | `POST /api/v1/native/vnpy/*` | vnpy_runtime | ⚠️ 可选安装 | ✅ acceptance | ⚠️ 中 | 环境重 | EXPERIMENTAL |
| Qlib 原生 | 原生 | `POST /api/v1/quantos/qlib/*` | qlib provider | ⚠️ 可选 | ✅ acceptance | ⚠️ 中 | — | EXPERIMENTAL |
| 新手五步向导 | 总览 | `PUT /api/v1/onboarding/profile` | investor_profile.json | ✅ 可用 | ✅ Phase3 | ✅ 高 | — | KEEP |
| 平台健康 | 系统 | `GET /api/v1/platform/health` | data_gate+jobs | ✅ 可用 | ⚠️ | ✅ 高 | — | KEEP |
| 系统体检 | 总览 | `POST /api/v1/system/doctor` | 多子系统 | ✅ 可用 | ✅ | ✅ 高 | — | KEEP |
| Netlify 静态站 | index.html 根 | Netlify Functions | — | ⚠️ 与 QuantOS 并行 | ✅ scenario-a | ⚠️ 低 | 双入口混淆 | REMOVE 或文档隔离 |

## 汇总

| 分类 | 数量 |
|---|---|
| KEEP | 14 |
| REBUILD | 5 |
| HIDE | 2 |
| REMOVE | 1 |
| EXPERIMENTAL | 4 |

## Mock / Fixture / Hardcoded 热点

| 位置 | 类型 | 生产风险 |
|---|---|---|
| `tools/china_quant/providers/fixture_provider.py` | FIXTURE | 仅 CLI `--fixture` 模式 |
| `data/gateway/live_snapshot.json` | blocked 缓存 | 非 mock，真实失败状态 |
| `config/gateway.yaml` demo_api_key | hardcoded dev key | 非生产 |
| `gateway/brokers/base.py` 瞬间 FILLED | 简化模拟 | Paper 非真实撮合 |
| `screener_backtest.py` pit_passed=True | 硬编码 | 回测可信度 |

## 无后端 / 未连接 API 按钮（已审计）

| 按钮 | 状态 |
|---|---|
| `market-update`（总览） | 已绑定 API（portal audit 误报 FRONTEND_EVENT_NOT_BOUND） |
| `paper-refresh` | 已绑定，缺 toast 反馈 |
| `open-pdf` | 客户端打开本地路径，无服务端 |
| `native-vnpy-start` 等 | 部分仅在 action-registry，index 用 data-action 覆盖 |
