# QuantOS CN — 安装与运行指南

> 产品主页：[README.md](../README.md) · 开源清单：[OPEN_SOURCE_MANIFEST.md](OPEN_SOURCE_MANIFEST.md) · 用户操作：[USER_GUIDE.md](USER_GUIDE.md)

本文档提供 **macOS / Linux / Windows** 完整安装步骤。按顺序执行即可在本地运行门户。

---

## 1. 环境要求

| 项目 | 最低要求 | 推荐 |
|------|----------|------|
| 操作系统 | macOS 12+、Ubuntu 20.04+、Windows 10/11 | macOS / Win11 |
| Python | 3.9+ | 3.11 |
| 内存 | 8 GB | 16 GB |
| 磁盘 | 5 GB 可用 | 20 GB（含 DuckDB 缓存） |
| 网络 | 拉取 AKShare / Tushare 行情 | 稳定宽带 |

**Windows 说明：** 原生支持 PowerShell 脚本（无需 WSL）。部分 macOS 专属调度（launchd）在 Windows 上可手动运行等价 Python 命令。

**可选：** [Tushare Pro](https://tushare.pro/) Token — 无 Token 时系统以 AKShare 为主数据源。

---

## 2. 获取代码

```bash
git clone https://github.com/kenzhao0621-tech/quantos-cn.git
cd quantos-cn
```

> 仓库名：**quantos-cn** · 克隆后目录可任意命名（如 `quantos-cn`）。

---

## 3. macOS / Linux 安装

### 3.1 一键引导

```bash
make bootstrap
cp .env.example .env
# 编辑 .env，填入 TUSHARE_TOKEN=你的token（推荐，可留空）
make app
```

浏览器自动打开：**http://127.0.0.1:8787/portal**

### 3.2 分步说明

| 步骤 | 命令 | 作用 |
|------|------|------|
| 创建虚拟环境 | `python3 -m venv .venv-china-quant` | 隔离依赖 |
| 安装依赖 | `make bootstrap` | 安装 pins + `pip install -e .` |
| 健康检查 | `make doctor` | 验证 gateway / quant 导入 |
| 启动门户 | `make app` | 启动 FastAPI + 打开浏览器 |
| 停止 | `make portal-stop` | 释放 8787 端口 |

### 3.3 无 Make 时（Linux 最小路径）

```bash
python3 -m venv .venv-china-quant
.venv-china-quant/bin/pip install -r requirements/requirements-china-quant-pins.txt
.venv-china-quant/bin/pip install -r requirements/requirements-gateway-pins.txt
.venv-china-quant/bin/pip install -e .
bash scripts/start-app.sh
```

---

## 4. Windows 安装

### 4.1 前置

1. 安装 [Python 3.11](https://www.python.org/downloads/windows/) — **勾选 “Add python.exe to PATH”**
2. 打开 **PowerShell**（建议“以管理员身份”首次安装依赖）
3. 若提示脚本被禁止：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 4.2 一键引导

```powershell
cd quantos-cn
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
copy .env.example .env
# 用记事本编辑 .env，填入 TUSHARE_TOKEN=
powershell -ExecutionPolicy Bypass -File scripts\start-app.ps1
```

浏览器打开：**http://127.0.0.1:8787/portal**

### 4.3 Windows 常用命令

| 操作 | 命令 |
|------|------|
| 启动 | `powershell -File scripts\start-app.ps1` |
| 仅启动 API | `powershell -File scripts\start-portal.ps1` |
| 停止 | `powershell -File scripts\stop-portal.ps1` |
| 健康检查 | 浏览器访问 `http://127.0.0.1:8787/health` |

### 4.4 Windows 路径说明

- 虚拟环境：`.venv-china-quant\Scripts\python.exe`
- 日志：`data\gateway\portal.log`
- 日报导出：`%USERPROFILE%\Desktop\China_A_Share_Daily_Reports`
- 自定义日报目录：设置环境变量 `QUANTOS_DESKTOP_REPORTS`

---

## 5. 配置 `.env`

从 `.env.example` 复制，**仅本地保存，不要提交 Git**：

```ini
# 推荐 — 提升日线/EOD 数据质量
TUSHARE_TOKEN=你的token

# 可选 — 覆盖日报桌面目录
# QUANTOS_DESKTOP_REPORTS=D:\Reports\QuantOS
```

---

## 6. 验证安装成功

```bash
# macOS / Linux
curl -s http://127.0.0.1:8787/health
curl -s -H "X-API-Key: demo-local-key-change-in-prod" http://127.0.0.1:8787/api/v1/gateway/capabilities | head
```

门户顶栏应显示：**模式**、**数据**、**实时** 状态 pill。

运行测试（可选）：

```bash
make test-gateway
# 或
.venv-china-quant/bin/python -m pytest tests/test_paper_live_desk.py -q
```

---

## 7. 首次使用三步

1. 打开门户 → **进入平台** → 确认风险提示  
2. **智能选股** → 资金 ¥5,000 → **收盘数据（快速）** → **运行选股**  
3. **模拟练习** → **启动模拟** → 将选股结果 **加入 Paper**

实时选股：选 **实时智能** → **运行实时智能选股**（首次约 20–90 秒拉取全市场报价）。

详细图文 → [USER_GUIDE.md](USER_GUIDE.md)

---

## 8. 常见问题

| 现象 | 处理 |
|------|------|
| `port 8787 already in use` | `make portal-stop` 或 Windows `stop-portal.ps1` |
| `venv missing` | 重新运行 bootstrap |
| 选股超时 | 休市后首次实时刷新较慢；2 分钟内重试走缓存；或先用收盘模式 |
| Windows `pip` 很慢 | 使用国内 PyPI 镜像或 VPN |
| AKShare 拉取失败 | 检查网络；稍后重试；配置 Tushare 作为补充 |
| 403 券商页 | 使用门户「备用官方链接」或券商 App 登录 |

---

## 9. 开源发布前自检

维护者推送 GitHub 前：

```bash
bash scripts/validate-open-source.sh
```

详见 [OPEN_SOURCE_MANIFEST.md](OPEN_SOURCE_MANIFEST.md)。
