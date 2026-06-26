# QuantOS CN

**中国 A 股智能量化选股与模拟交易平台** · 本地运行 · 开源 MIT

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Gateway 2.1](https://img.shields.io/badge/gateway-2.1.0-purple.svg)](#技术特点)
[![macOS](https://img.shields.io/badge/macOS-✓-black.svg)](#安装与启动)
[![Windows](https://img.shields.io/badge/Windows-✓-0078D6.svg)](#windows-安装)

**仓库：** https://github.com/kenzhao0621-tech/quantos-cn

---

## 目录

- [这是什么](#这是什么)
- [核心功能](#核心功能)
- [界面预览](#界面预览)
- [技术特点](#技术特点)
- [系统架构](#系统架构)
- [安装与启动](#安装与启动)
- [三分钟上手](#三分钟上手)
- [页面说明](#页面说明)
- [常用命令](#常用命令)
- [主要 API](#主要-api)
- [项目结构](#项目结构)
- [文档索引](#文档索引)
- [隐私与安全](#隐私与安全)
- [English](#english)

---

## 这是什么

**QuantOS CN** 是一套在你电脑上运行的 **A 股量化工作台**：

- 用 **多因子模型 + AI 智能体** 筛选股票
- 用 **真实行情** 做 Paper 模拟（T+1、费用、涨跌停）
- 用 **策略验证** 回看昨日选股表现并自动学习调参
- 用 **券商助手** 预填订单（**绝不自动扣款**）

> 不是云端黑盒投顾，不承诺收益，不自动真实下单。

---

## 核心功能

| 功能 | 你能得到什么 |
|------|-------------|
| **智能选股** | 收盘模式 ~1 秒出结果；实时模式一键刷新全市场 + 选股 |
| **行级解读** | 点击任意推荐股票 → 弹窗查看因子得分、智能体评语 |
| **实时行情** | 交易时段每 15 分钟后台自动刷新 AKShare 全市场报价 |
| **Paper 模拟** | 零真实资金验证 T+1、手续费、涨跌停、自动买卖信号 |
| **策略验证** | T+1 回测昨日选股；自验证学习循环给出参数建议 |
| **PDF 报告** | 个股选股分析 PDF、量化日报 MD/HTML/PDF |
| **券商辅助** | 打开官方交易页 / 导出 CSV / QMT 落单（须本人确认） |

---

## 界面预览

| 总览 | 数据同步 |
|:---:|:---:|
| ![总览](docs/assets/screenshots/01_overview.png) | ![数据](docs/assets/screenshots/02_market.png) |

| 任务日报 | Paper 模拟 | 智能选股 |
|:---:|:---:|:---:|
| ![任务](docs/assets/screenshots/03_job.png) | ![Paper](docs/assets/screenshots/04_paper.png) | ![选股](docs/assets/screenshots/05_screener.png) |

---

## 技术特点

| 特点 | 说明 |
|------|------|
| **本地数据主权** | DuckDB 本地仓库；`data/` 不入 Git，克隆后自行拉取 |
| **双源行情** | Tushare Pro + AKShare Sina；休市智能降级，避免超时 |
| **会话感知刷新** | 开盘 `require_live` 校验；休市单次拉取（~20s 而非 3min） |
| **TradingAgents-CN** | 选股结果叠加多空/风险智能体评审 |
| **学习闭环** | `POST /api/v1/screener/learn` 验证历史并建议调参 |
| **A 股规则引擎** | T+1 · 100 股整数倍 · 涨跌停 · 行业分散 |
| **Gateway 2.1** | 统一 REST · RBAC · 审计 · 能力清单 API |
| **跨平台** | macOS/Linux `Makefile` + Windows PowerShell 脚本 |
| **零构建前端** | Vanilla JS，改完刷新浏览器即可 |

---

## 系统架构

```
行情源 (Tushare / AKShare)
        ↓
   DuckDB 本地仓库 + live_snapshot.json
        ↓
   quant 选股引擎 ──→ TradingAgents 叠加
        ↓
   gateway REST API (FastAPI)
        ↓
   portal-web 中文门户
        ↓
   Paper 模拟 / PDF / 券商 handoff
```

**技术栈：** FastAPI · DuckDB · pandas · AKShare · Tushare · pytest

---

## 安装与启动

### 环境要求

| 项目 | 要求 |
|------|------|
| 系统 | macOS / Linux / **Windows 10+** |
| Python | 3.9+（推荐 3.11） |
| 内存 | 8 GB+ |
| 可选 | [Tushare Pro](https://tushare.pro/) Token |

### macOS / Linux

```bash
git clone https://github.com/kenzhao0621-tech/quantos-cn.git
cd quantos-cn

make bootstrap
cp .env.example .env          # 填入 TUSHARE_TOKEN（推荐）
make app
```

打开：**http://127.0.0.1:8787/portal**

### Windows 安装

```powershell
git clone https://github.com/kenzhao0621-tech/quantos-cn.git
cd quantos-cn

powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
copy .env.example .env
powershell -ExecutionPolicy Bypass -File scripts\start-app.ps1
```

完整 FAQ 与分步说明 → **[docs/INSTALL.md](docs/INSTALL.md)**

---

## 三分钟上手

```
① 进入平台 → 确认风险提示
② 智能选股 → 资金 ¥5,000 →「收盘数据」→ 运行选股
③ 点击股票行 → 查看得分与理由
④ 模拟练习 → 启动 Paper → 加入模拟组合
⑤ 策略验证 → 验证昨日选股 / 自验证学习
```

---

## 页面说明

| 标签 | 用途 |
|------|------|
| **智能选股** | 收盘/实时选股、行级详情、PDF、加入 Paper |
| **策略验证** | 昨日验证、学习循环、参数建议 |
| **模拟练习** | Paper 持仓、自动盯盘、买卖信号 |
| **券商助手** | 连接券商、辅助填单（人工确认） |
| **使用指南** | 内置帮助与免责 |
| **高级·总览** | 系统状态、日报下载 |
| **高级·数据** | 行情同步、实时刷新 |

用户手册 → **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**

---

## 常用命令

```bash
make doctor          # 环境检查
make app             # 启动门户
make portal-stop     # 停止
make daily-report    # 生成量化日报
make test-gateway    # 回归测试
```

Windows：`scripts\start-app.ps1` · `scripts\stop-portal.ps1`

API 文档：http://127.0.0.1:8787/docs

---

## 主要 API

| 端点 | 说明 |
|------|------|
| `GET /api/v1/screener/run` | 运行选股（`mode=live` 含实时行情） |
| `POST /api/v1/screener/learn` | 策略自验证 + 学习建议 |
| `POST /api/v1/screener/report/{symbol}` | 个股选股 PDF |
| `POST /api/v1/market/live-refresh` | 手动刷新全市场报价 |
| `GET /api/v1/gateway/capabilities` | Gateway 能力清单 |

---

## 项目结构

```
quantos-cn/
├── apps/portal-web/     # 中文 Web 门户
├── gateway/             # FastAPI 网关
├── quant/               # 选股、行情、日报引擎
├── integrations/        # vn.py / Qlib 适配
├── requirements/        # Python 依赖 pins
├── scripts/             # 启动脚本 (.sh + .ps1)
├── tests/               # pytest
└── docs/                # 安装指南、用户手册、截图
```

→ **[docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)**

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/INSTALL.md](docs/INSTALL.md) | macOS / Windows 安装 |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | 页面流程与 FAQ |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构与数据流 |
| [docs/OPEN_SOURCE_MANIFEST.md](docs/OPEN_SOURCE_MANIFEST.md) | 开源范围与隐私 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |

---

## 隐私与安全

- `.env`、`.venv/`、`data/` **不入 Git** — 密钥与行情库仅留本地
- 不存储交易密码、短信验证码
- 不构成投资建议；真实下单须本人在券商 App 确认
- 生产部署前请更换默认 API Key `demo-local-key-change-in-prod`

---

## English

**QuantOS CN** is a local-first China A-share quant platform: multi-factor screener, live quotes, paper trading (T+1 rules), and broker-assist handoff.

```bash
git clone https://github.com/kenzhao0621-tech/quantos-cn.git && cd quantos-cn
make bootstrap && cp .env.example .env && make app
```

---

## License

[MIT License](LICENSE)

---

**投资有风险，决策需谨慎。QuantOS CN 为研究与模拟辅助工具，不构成投资建议。**
