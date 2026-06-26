<div align="center">

# QuantOS CN

### 中国 A 股智能量化选股与模拟交易平台

**本地优先 · 多因子选股 · 实时行情 · Paper 验证 · 人工确认辅助实盘**

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Gateway 2.1](https://img.shields.io/badge/gateway-2.1.0-purple.svg)](#技术栈)

[中文快速开始](#-快速开始) · [English](#-english-quick-start) · [项目结构](docs/PROJECT_STRUCTURE.md) · [用户指南](docs/USER_GUIDE.md) · [架构](docs/ARCHITECTURE.md)

</div>

---

## 这是什么？

**QuantOS CN**（仓库名 `quantos-cn`）是一套面向中国 A 股的**本地量化工作台**：

| 你能做什么 | 说明 |
|-----------|------|
| **智能选股** | 多因子 + Alpha158-lite + TradingAgents-CN 叠加；收盘快速 / 实时一键选股 |
| **实时行情** | 盘中自动 15 分钟刷新；选股时内置刷新，无需先切页面 |
| **Paper 模拟** | T+1、费用、涨跌停规则；真实行情盯盘与买卖信号 |
| **策略自验证** | T+1 回测昨日选股 + 智能体给出参数调整建议 |
| **PDF 报告** | 量化日报、个股选股分析 PDF |
| **券商辅助** | 浏览器 handoff 预填订单（**不自动扣款**） |

> **不是**云端黑盒投顾，**不承诺收益**，**不自动真实下单**。真实交易须在券商 App 由你本人确认。

---

## ✨ 核心亮点（v4.1）

- **一键实时智能选股** — 刷新行情 + 运行选股在同一次点击完成
- **后台盘中刷新** — Gateway 启动后，交易时段每 15 分钟自动拉取真实报价
- **TradingAgents-CN** — 选股结果叠加多空/风险智能体评审
- **科研级学习循环** — `POST /api/v1/screener/learn` 验证历史策略并建议调参
- **灵敏 Paper 信号** — 放宽买卖区间、动量入场、止盈/止损更及时
- **Gateway 2.1** — 统一能力清单 `GET /api/v1/gateway/capabilities`

---

## 🚀 快速开始

### 环境要求

| 项目 | 要求 |
|------|------|
| 系统 | macOS / Linux（Windows 建议 WSL） |
| Python | 3.9+（推荐 3.11） |
| 内存 | 8 GB+ |
| 可选 | [Tushare Pro](https://tushare.pro/) Token（无则部分走 AKShare） |

### 1. 克隆与安装

```bash
git clone https://github.com/kenzhao0621-tech/quantos-cn.git
cd quantos-cn

make bootstrap
cp .env.example .env
# 编辑 .env，填入 TUSHARE_TOKEN（推荐）
```

### 2. 启动门户

```bash
make app
```

浏览器打开：**http://127.0.0.1:8787/portal**

### 3. 新手四步（5 分钟上手）

```
① 登录 → 选「新手投资者」→ 确认风险提示
② 「新手入门」→ 点击「更新数据」（拉取/同步行情到本地 DuckDB）
③ 「智能选股」→ 设资金（如 ¥5,000）→ 选「实时智能」→「运行实时智能选股」
④ 「模拟练习」→ 启动 Paper →「加入 Paper 模拟组合」→ 观察自动盯盘
```

详细图文 → **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**

### 4. 常用命令

```bash
make doctor              # 检查环境与包版本
make daily-report        # 生成量化日报（MD/HTML/PDF）
make test-gateway        # 网关回归测试
make paper-start         # CLI 启动 Paper

# API 文档（需先 make app）
open http://127.0.0.1:8787/docs
```

---

## 🖼️ 界面与功能地图

| 标签页 | 功能 |
|--------|------|
| 新手入门 | 四步向导、数据更新、环境检查 |
| 总览 | 系统状态、最新日报、快捷入口 |
| 智能选股 | 收盘/实时选股、自验证学习、导出 PDF、加入 Paper |
| 模拟练习 | Paper 持仓、15 分钟自动行情、自动盯盘 |
| 券商助手 | 只读连接、订单票据、浏览器辅助填单 |
| 模型实验室 | 样本外验证、过拟合检测 |

截图：`docs/ai/v6/screenshots/` · E2E 报告：`docs/ai/v6/`

---

## 🏗️ 技术栈

```
quantos-cn/
├── apps/portal-web/       # 中文 Web 门户
├── gateway/               # FastAPI 网关（Paper、风控、学习、监控）
├── quant/                 # 选股引擎、行情、日报、PDF
├── integrations/          # vn.py / Qlib 可选适配
├── config/                # gateway.yaml
├── scripts/               # 启动与流水线
├── tests/                 # pytest 测试
├── docs/                  # 文档与验收
└── legacy/netlify/        # 历史 Netlify 演示（非主产品）
```

完整目录说明 → **[docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)**

| 层级 | 技术 |
|------|------|
| API | FastAPI · Uvicorn · Pydantic v2 |
| 数据 | DuckDB · pandas · Tushare · AKShare |
| 前端 | HTML / CSS / JavaScript（无构建） |
| 智能体 | TradingAgents-CN 桥接 |
| 测试 | pytest · Playwright |
| Python 包 | `pip install -e .` → `quantos-cn` |

### 架构简图

```
行情源 (Tushare/AKShare)
        ↓
   DuckDB 本地仓库
        ↓
  quant 选股引擎 ──→ TradingAgents 叠加
        ↓
  gateway REST API
        ↓
  portal-web 门户 ──→ Paper 模拟 / PDF / 券商 handoff
```

---

## 📡 主要 API（节选）

| 端点 | 说明 |
|------|------|
| `GET /api/v1/screener/run` | 运行选股（`mode=live` 含实时行情） |
| `POST /api/v1/screener/learn` | 策略自验证 + 学习建议 |
| `POST /api/v1/screener/report/{symbol}` | 生成个股选股 PDF |
| `POST /api/v1/market/live-refresh` | 手动刷新全市场报价 |
| `GET /api/v1/gateway/capabilities` | Gateway 能力清单 |
| `GET /api/v1/research/reports/download` | 下载量化日报 PDF |

---

## 📚 文档导航

| 文档 | 适合 |
|------|------|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | **所有用户** — 安装、页面、FAQ |
| [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) | **开发者** — 目录与模块 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | **开发者** — 数据流与边界 |
| [docs/COMPARISON.md](docs/COMPARISON.md) | **选型者** — 与云端/vn.py 对比 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | **贡献者** — PR 与测试 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更 |

---

## 🔒 安全与合规

- 不构成投资建议；模型输出仅供参考
- **不自动真实下单**；无人值守默认关闭
- **不存储**交易密码、短信验证码
- A 股规则：T+1、100 股整数倍、涨跌停拦截
- 运行时数据（`data/`、`.env`）**勿提交 Git**

---

## 🗺️ 路线图

- [x] 多因子选股 + 实时一键选股 + TradingAgents 叠加
- [x] 盘中 15 分钟后台行情刷新
- [x] 策略自验证学习循环 + 选股 PDF
- [x] Paper 灵敏买卖信号
- [ ] 经济样本外验证达标（`PRODUCTION_READY`）
- [ ] Docker 一键镜像 · 英文完整文档

---

## 🤝 贡献

欢迎 Issue 与 PR。请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

```bash
git checkout -b feat/your-feature
make test-gateway
# conventional commits: feat: / fix: / docs:
```

---

## 📦 GitHub 发布说明

**仓库 Topics 建议：** `quantitative-finance` `a-share` `stock-screener` `fastapi` `duckdb` `paper-trading` `tushare` `quant-trading`

**Release tag 示例：** `v4.1.0` — 见 [CHANGELOG.md](CHANGELOG.md)

**从旧仓库迁移：** 原 `netlify-demo` 已更名为 `quantos-cn`；Netlify 静态演示移至 `legacy/netlify/`。

---

## 🌐 English Quick Start

**QuantOS CN** is a local-first China A-share quant platform: multi-factor screener, live quotes, paper trading with T+1 rules, and broker-assist handoff (manual confirm only — no auto live trading).

```bash
git clone https://github.com/kenzhao0621-tech/quantos-cn.git
cd quantos-cn
make bootstrap && cp .env.example .env
make app
# Open http://127.0.0.1:8787/portal
```

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for the full walkthrough.

---

## 📄 License

[MIT License](LICENSE)

---

<div align="center">

**投资有风险，决策需谨慎。QuantOS CN 为研究与模拟辅助工具，不构成投资建议。**

Made for A-share quant researchers and learners

</div>
