# QuantOS CN

**中国 A 股智能量化选股与模拟交易平台** · 本地运行 · 开源 MIT

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![QuantOS v2.3](https://img.shields.io/badge/QuantOS-v2.3-purple.svg)](#v23-统一架构)
[![macOS](https://img.shields.io/badge/macOS-✓-black.svg)](#安装与启动)
[![Windows](https://img.shields.io/badge/Windows-✓-0078D6.svg)](#windows-安装)

**GitHub：** https://github.com/kenzhao0621-tech/quantos-cn

---

## 目录

- [这是什么](#这是什么)
- [v2.3 统一架构](#v23-统一架构)
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

- 用 **固定公式多因子评分 + Kronos 预测 + 九角色智能体** 分析个股
- 用 **可验证数据来源（DataTruthOS）** 标注每条数据的出处与新鲜度
- 用 **真实或降级行情** 做 Paper 模拟（T+1、费用、涨跌停）
- 用 **策略验证** 回看历史选股表现，不伪造回测收益
- 用 **券商助手** 预填订单（**绝不自动扣款**）

> 不是云端黑盒投顾，不承诺收益，不自动真实下单。缺失数据会诚实标注「降级」，不会编造行情或预测。

---

## v2.3 统一架构

v2.3 将 **Kronos/Agents 重构** 与 **CacheOS/ScoringOS 固定权重公式** 合并为一条管线：

```
DataOS → DataTruthOS → CacheOS → ComputeOS → FeatureOS
  → KronosOS（可选）→ AgentsOS（可选）→ ScoringOS → RiskOS → ExplainOS
```

| 模块 | 作用 |
|------|------|
| **DataTruthOS** | 国内数据必须携带 `source_url`、`updated_at`、`fetched_at`、`data_version`、`quality_level` |
| **CacheOS** | L0/L1 缓存、预测缓存、按数据版本自动失效 |
| **ScoringOS** | 固定公式：`基础分 × 市场环境 × 数据质量 − 风险 − 执行 − 过热` |
| **ExplainOS** | 四面板可复现评分卡（因子权重、来源、交易计划） |
| **KronosOS** | K 线分布预测；sidecar 不可用时降级并标 `degraded` |
| **AgentsOS** | 九角色结构化分析；RiskManager 可一票否决 |

**公式版本：** `v2.3_integrated_conservative_ashare`

**安全默认：** `PAPER_TRADING_ONLY=true`，`REAL_MONEY_EXECUTION_DISABLED=true`（实盘功能保留但默认关闭）

---

## 核心功能

| 功能 | 你能得到什么 |
|------|-------------|
| **智能选股** | 收盘模式快速出结果；实时模式刷新全市场后选股 |
| **v2.3 评分卡** | 个股弹窗展示固定公式分解、缓存状态、数据来源 |
| **Kronos 预测** | 5 日方向/波动分布（预测不保证发生，降级时置信度封顶） |
| **多智能体研究** | 技术/基本面/舆情/多空辩论/风险经理等九角色 JSON 输出 |
| **实时行情** | 交易时段 AKShare 新浪全市场报价（休市自动降级） |
| **Paper 模拟** | 零真实资金验证 T+1、手续费、涨跌停 |
| **策略验证** | 真实基准回测；跑输基准时如实 `BLOCKED_BY_VALIDATION` |
| **PDF 报告** | 个股分析 PDF、量化日报 |
| **券商辅助** | 打开官方交易页 / 导出 CSV（须本人确认） |

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
| **数据可追溯** | DataTruthOS 门禁 + `config/source_registry.yaml` 来源注册表 |
| **评分可复现** | 固定权重 YAML + 确定性公式，同一输入同一分数 |
| **缓存可观测** | `GET /api/v1/advisory/cache-status` 查看命中率与策略 |
| **本地数据主权** | DuckDB 本地仓库；`data/` 不入 Git，克隆后自行拉取 |
| **双源行情** | Tushare Pro + AKShare Sina；休市智能降级 |
| **Kronos sidecar** | Python 3.12 独立 venv（`.venv-kronos`），主环境保持 3.9 |
| **A 股规则引擎** | T+1 · 100 股整数倍 · 涨跌停 · 行业分散 |
| **跨平台** | macOS/Linux `Makefile` + Windows PowerShell 脚本 |

---

## 系统架构

```
行情源 (Tushare / AKShare / 可选 RQData)
        ↓
   DuckDB 本地仓库 + live_snapshot（本地，不入 Git）
        ↓
   DataTruthOS 验证 → CacheOS / ComputeOS
        ↓
   ScoringOS 固定公式 + KronosOS + AgentsOS
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
| Python | 3.9+（主环境）；Kronos 可选 3.12 sidecar |
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

完整 FAQ → **[docs/INSTALL.md](docs/INSTALL.md)**

### 可选：Kronos 真实推理

```bash
# 需要 Python 3.12 + torch（见 quant/models/kronos/README 或 Phase 3 文档）
python3.12 -m venv .venv-kronos
.venv-kronos/bin/pip install -r requirements/kronos-sidecar.txt
```

未安装 sidecar 时，Kronos 自动使用统计降级路径，输出标 `degraded: true`。

---

## 三分钟上手

```
① 进入平台 → 确认风险提示
② 智能选股 → 设置资金 →「收盘数据」→ 运行选股
③ 点击股票行 → 查看因子得分、v2.3 评分卡、智能体评语
④ 模拟练习 → 启动 Paper → 加入模拟组合
⑤ 策略验证 → 验证历史选股表现
```

---

## 页面说明

| 标签 | 用途 |
|------|------|
| **智能选股** | 收盘/实时选股、行级详情、v2.3 评分卡、加入 Paper |
| **策略验证** | 历史验证、学习循环、参数建议 |
| **模拟练习** | Paper 持仓、自动盯盘、买卖信号 |
| **研究报告** | 个股多智能体研究、风险中心 |
| **券商助手** | 连接券商、辅助填单（人工确认） |
| **高级·数据** | 行情同步、实时刷新 |

用户手册 → **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**

---

## 常用命令

```bash
make doctor          # 环境检查
make app             # 启动门户（http://127.0.0.1:8787/portal）
make portal-stop     # 停止
make daily-report    # 生成量化日报
make test-gateway    # 回归测试
```

推送前隐私扫描：

```bash
bash scripts/validate-open-source.sh
```

API 文档：http://127.0.0.1:8787/docs

---

## 主要 API

| 端点 | 说明 |
|------|------|
| `GET /api/v1/screener/run` | 运行选股（`mode=live` 含实时行情） |
| `GET /api/v1/advisory/analyze` | v2.3 个股建议（公式分解 + DataTruth + 可选 Kronos/Agents） |
| `GET /api/v1/advisory/cache-status` | CacheOS 命中率与策略 |
| `POST /api/v1/market/live-refresh` | 手动刷新全市场报价（交易时段） |
| `POST /api/v1/screener/learn` | 策略自验证 + 学习建议 |
| `GET /api/v1/gateway/capabilities` | Gateway 能力清单 |

Advisory 参数：`symbol`、`capital_cny`、`include_kronos`、`include_agents`、`force_refresh`

---

## 项目结构

```
quantos-cn/
├── apps/portal-web/       # 中文 Web 门户
├── gateway/               # FastAPI 网关 + AgentsOS
├── quant/
│   ├── cache_os/          # 缓存层
│   ├── compute_os/        # 增量计算 DAG
│   ├── scoring_os/        # 固定评分公式
│   ├── explain_os/        # 解释卡片
│   ├── data_truth_os/     # 数据来源验证
│   ├── models/kronos/     # Kronos 预测
│   └── application/       # AdvisoryService 等
├── config/                # routing、权重、来源注册表
├── requirements/          # Python 依赖
├── scripts/               # 启动与验证脚本
├── tests/                 # pytest
└── docs/                  # 安装指南、集成审计、交付报告
```

→ **[docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)**  
→ v2.3 集成报告：**[docs/integration_audit/FINAL_INTEGRATION_REPORT.md](docs/integration_audit/FINAL_INTEGRATION_REPORT.md)**

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/INSTALL.md](docs/INSTALL.md) | macOS / Windows 安装 |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | 页面流程与 FAQ |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构与数据流 |
| [docs/integration_audit/](docs/integration_audit/) | v2.3 分支合并与 DataTruth 集成报告 |
| [docs/refactor_audit/](docs/refactor_audit/) | Kronos/Agents Phase 0–8 审计 |
| [docs/OPEN_SOURCE_MANIFEST.md](docs/OPEN_SOURCE_MANIFEST.md) | 开源范围与隐私 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |

---

## 隐私与安全

- `.env`、`.venv*`、`data/` **不入 Git** — 密钥与行情库仅留本地
- 不存储交易密码、短信验证码
- 不构成投资建议；真实下单须本人在券商 App 确认
- 生产部署前请更换默认 API Key（见 `.env.example`）
- 推送前运行 `scripts/validate-open-source.sh` 检查路径与密钥泄露

---

## English

**QuantOS CN** is a local-first China A-share quant platform: reproducible multi-factor scoring (v2.3), DataTruth provenance, optional Kronos forecasts and multi-agent research, paper trading with T+1 rules, and broker-assist handoff. Live execution is disabled by default.

```bash
git clone https://github.com/kenzhao0621-tech/quantos-cn.git && cd quantos-cn
make bootstrap && cp .env.example .env && make app
```

---

## License

[MIT License](LICENSE)

---

**投资有风险，决策需谨慎。QuantOS CN 为研究与模拟辅助工具，不构成投资建议。**
