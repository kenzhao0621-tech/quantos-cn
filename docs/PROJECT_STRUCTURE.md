# QuantOS CN — 项目结构说明

> 仓库名：**quantos-cn** · Python 包名：`quantos-cn` · 产品名：**QuantOS CN**

## 顶层目录

```
quantos-cn/
├── apps/portal-web/          # 中文 Web 门户（Vanilla JS，无构建步骤）
├── gateway/                  # FastAPI 网关：API、Paper、券商、风控、学习循环
├── quant/                    # A 股量化引擎：选股、评分、日报、实时行情
├── integrations/             # vn.py / Qlib 可选原生适配
├── config/                   # gateway.yaml、市场规则
├── configs/                  # 因子注册表等 YAML 配置
├── scripts/                  # 启动、E2E、日报流水线
├── tests/                    # 单元与集成测试
├── docs/                     # 用户指南、架构、验收报告
├── legacy/netlify/           # 历史 Netlify 静态演示（非主产品）
├── Makefile                  # 一键 bootstrap / app / test
├── pyproject.toml            # pip install -e .
└── README.md                 # 入门文档（从这里开始）
```

## 核心数据流

```
Tushare / AKShare
       ↓
data/warehouse/quant.duckdb   ← 本地 DuckDB（运行后生成，不入库）
       ↓
quant/application/screener_service.py   ← 多因子 + TradingAgents 叠加
       ↓
gateway/api/bff_market.py     ← REST API
       ↓
apps/portal-web/              ← 浏览器门户
       ↓
gateway/paper/                ← Paper 模拟（T+1、真实行情盯盘）
```

## 重要模块

| 路径 | 职责 |
|------|------|
| `quant/paths.py` | 跨平台路径（桌面日报目录等） |
| `quant/application/live_market_service.py` | 全市场实时行情刷新与就绪检测 |
| `quant/application/screener_service.py` | 智能选股主引擎 |
| `gateway/agents/cn_research/` | TradingAgents-CN 研究智能体桥接 |
| `gateway/learning/screener_learning.py` | T+1 自验证 + 策略学习建议 |
| `gateway/monitoring/intraday_background.py` | 盘中每 15 分钟后台刷新行情 |
| `gateway/paper/autopilot_monitor.py` | Paper 自动盯盘买卖信号 |
| `quant/screener/screener_report_pdf.py` | 个股选股分析 PDF |

## 运行时目录（勿提交 Git）

| 路径 | 说明 |
|------|------|
| `data/warehouse/` | DuckDB 数据库 |
| `data/gateway/` | Paper 状态、监控、审计运行时 |
| `artifacts/` | 学习报告、闭环验收 JSON |
| `.venv-china-quant/` | Python 虚拟环境 |
| `.env` | Tushare Token 等密钥 |

## API 入口

启动后：

- 门户：`http://127.0.0.1:8787/portal`
- OpenAPI：`http://127.0.0.1:8787/docs`
- 能力清单：`GET /api/v1/gateway/capabilities`

## 文档索引

| 文档 | 读者 |
|------|------|
| [README.md](../README.md) | 所有人 — 快速开始 |
| [OPEN_SOURCE_MANIFEST.md](OPEN_SOURCE_MANIFEST.md) | 维护者 — 开源范围与隐私 |
| [INSTALL.md](INSTALL.md) | 所有人 — macOS / Windows 安装 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 开发者 — 架构 |
| [COMPARISON.md](COMPARISON.md) | 选型 — 与同类产品对比 |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 贡献者 |
