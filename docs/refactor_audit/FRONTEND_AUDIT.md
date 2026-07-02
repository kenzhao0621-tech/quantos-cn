# FRONTEND_AUDIT — 前端审计

> 结论先行：原生 JS 单页应用，7 个可用页面功能真实、免责声明完整、无违禁措辞（KEEP）；5 个孤儿页面有数据刷新逻辑但无导航入口；无图表能力（仅 SVG sparkline）；对照重构文档 §11 六大核心页面缺 Backtest Report 可视化与 Risk Center 入口。

## 1. 文件结构

| 文件 | 角色 | 状态 |
|---|---|---|
| `index.html` | 布局 + 法律声明 overlay（L13–27） | KEEP |
| `app.js`（~1858 行） | 路由、动作分发、刷新编排 | KEEP+PATCH |
| `ui-render.js` | DOM 渲染、sparkline（L192–202）、弹窗 | KEEP |
| `viewmodels.js` | API → 中文标签转换 | KEEP |
| `api-client.js` | envelope HTTP、超时、demo key | KEEP（demo key 发布前处理） |
| `action-registry.js` | 动作 → 端点映射 | KEEP |

## 2. 页面清单

### 可导航（7 个，功能真实）

| 页面 | 标签 | 内容 |
|---|---|---|
| page-screener | 智能选股 | 偏好、搜索、选股表、个股弹窗、工单（默认落地页） |
| page-models | 策略验证 | T+1 证明、学习循环、模型注册表、生产验证、回测 |
| page-paper | 模拟练习 | 纸上下单、15 分钟自动监控、持仓/成交 |
| page-brokers | 券商助手 | 向导、门控、执行路径 |
| page-help | 使用指南 | 帮助 + 免责 |
| page-overview | 高级·总览 | 系统状态、doctor、模式控制、halt |
| page-market | 高级·数据 | 同步、实时行情、指数、providers |

### 孤儿页（5 个 — Phase 7 处置）

page-reports / page-agents / page-native / page-shadow / page-risk：有刷新函数（`app.js` L1356–1795 区间）但导航无 tab。**Phase 7 决策：reports 与 risk 恢复导航（对应重构文档 Backtest Report 与 Risk Center）；agents 并入新增建议页；native/shadow 保持高级折叠。**

## 3. 具体问题

| 问题 | 证据 | 处置 |
|---|---|---|
| 回测日期硬编码 | `app.js` L113–116 `as_of_date: "2026-06-16"` | Phase 7 动态取最新交易日 |
| 无图表库 | 仅 `sparklineSvg()`；无收益曲线/回撤曲线/K 线 | Phase 7 引入轻量图表（如原生 SVG 扩展或 uPlot）渲染回测收益/回撤曲线 |
| "Alpha158-lite" 标签误导 | UI 展示与实际 5 因子混合不符 | Phase 2 改名后同步 UI |
| 预期收益区间来源不透明 | 依赖 bucket_stats 工件，缺失时需确认 UI 显示 INSUFFICIENT_HISTORY | Phase 7 验证 |
| demo API key 内置 | `api-client.js` L7 | 发布前处理 |

## 4. 对照重构文档 §11 核心页面

| 目标页面 | 现状 | Phase 7 计划 |
|---|---|---|
| Dashboard | page-overview approximates | 补今日候选数、风险警报卡片 |
| Research Lab | page-models 部分 | 补模型选择、参数对比、指标解释 |
| Stock Advisor | 个股弹窗部分 | 升级为 A/B/C/D/BLOCKED 评级 + 多空理由 + 失效条件（AgentsOS 输出） |
| Portfolio Builder | 无独立页 | 基于 `quant/portfolio/unified.py` 新增候选池+仓位+行业分布 |
| Backtest Report | page-models 内嵌表格 | 恢复 page-reports 导航 + 收益/回撤曲线 + benchmark 对比 |
| Risk Center | page-risk 孤儿 | 恢复导航 + 黑名单/数据异常/禁止交易原因 |

## 5. 措辞与新手友好

- ✅ 无"保证收益/稳赚/必涨"；免责声明四处覆盖。
- ⚠️ 新手解释（为什么推荐、可能错在哪、失效条件、最多投入比例）目前只有部分弹窗文案 —— Phase 6 AgentsOS 输出 + Phase 7 渲染统一补齐。
