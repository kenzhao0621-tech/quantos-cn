# QuantOS CN — 开源发布清单

本文档说明 **GitHub 仓库中包含什么、不包含什么**，便于审核隐私与合规。

## 包含（开源代码与文档）

| 类别 | 路径 | 说明 |
|------|------|------|
| Web 门户 | `apps/portal-web/` | 中文量化工作台 UI |
| API 网关 | `gateway/` | FastAPI、Paper、风控、学习循环 |
| 量化引擎 | `quant/` | 选股、行情、日报、PDF |
| 集成适配 | `integrations/` | vn.py / Qlib 可选桥接 |
| 配置模板 | `config/`、`configs/`、`.env.example` | **无真实密钥** |
| 脚本 | `scripts/` | macOS/Linux bash + Windows PowerShell |
| 测试 | `tests/` | pytest 回归 |
| 文档 | `docs/` | 用户指南、架构、验收报告（脱敏路径） |
| 截图 | `docs/ai/v6/screenshots/` | 门户功能截图（无个人信息） |
| 历史演示 | `legacy/netlify/` | 旧 Netlify 静态站（非主产品） |

## 不包含（本地运行时生成，已在 `.gitignore`）

| 类别 | 路径 | 说明 |
|------|------|------|
| 虚拟环境 | `.venv-china-quant/` | `make bootstrap` 本地创建 |
| 密钥 | `.env` | Tushare Token 等，**切勿提交** |
| 行情数据库 | `data/warehouse/` | DuckDB，克隆后自行拉取 |
| Paper 状态 | `data/gateway/` | 模拟持仓、订单、日志 |
| 审计流水 | `docs/ai/gateway/audit/` | 本地 API 审计 |
| 交易账本 | `docs/ai/daily-trading/*LEDGER*` | 个人模拟记录 |
| 记忆库 | `memory/documents/`、`memory/runs/` | 本地 RAG / 运行摘要 |
| HAR 抓包 | `docs/ai/v6/har/` | 浏览器调试文件 |

## 隐私检查项

克隆后可在仓库根目录运行：

```bash
bash scripts/validate-open-source.sh
```

脚本会扫描 **源码与配置**（不含 `docs/ai/` 历史验收 JSON）中的：

- 绝对用户路径（如 `/Users/...`）
- 常见邮箱模式
- 已提交的 `.env` 文件

## 默认 API Key

开发模式使用占位 Key：`demo-local-key-change-in-prod`。  
**生产部署前必须在 `config/gateway.yaml` 或环境变量中更换。**

## 桌面日报目录

导出路径默认为：

- macOS：`~/Desktop/China_A_Share_Daily_Reports`
- Windows：`%USERPROFILE%\Desktop\China_A_Share_Daily_Reports`

可通过环境变量 `QUANTOS_DESKTOP_REPORTS` 覆盖。
