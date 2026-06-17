# QuantOS CN 架构说明

面向开发者与二次集成方。用户操作请参阅 [USER_GUIDE.md](USER_GUIDE.md)。

---

## 总览

```text
┌─────────────────────────────────────────────────────────────┐
│  apps/portal-web          中文 Web 门户 (8787/portal)        │
└───────────────────────────────┬─────────────────────────────┘
                                │ REST + X-API-Key
┌───────────────────────────────▼─────────────────────────────┐
│  gateway/api/app.py       FastAPI 统一入口                   │
│  ├── operations.py        系统、Paper、券商、偏好、门控      │
│  ├── bff_market.py        行情、选股、自选                   │
│  └── envelope             统一 ok/error 响应                 │
└───────┬─────────────────┬─────────────────┬───────────────┘
        │                 │                 │
┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────────────┐
│ quant/       │  │ gateway/     │  │ integrations/        │
│ screener     │  │ paper/       │  │ vnpy · qlib 适配       │
│ scoring      │  │ brokers/     │  │ services/vnpy_runtime  │
│ validation   │  │ risk/        │  └──────────────────────┘
│ daily_report │  │ live_trading/│
└───────┬──────┘  └───────┬──────┘
        │                 │
        └────────┬────────┘
                 ▼
        data/warehouse/quant.duckdb
        data/gateway/*.json (运行时，gitignore)
```

---

## 模块职责

| 路径 | 职责 |
|------|------|
| `gateway/api/` | HTTP 路由、RBAC、审计 |
| `gateway/paper/` | Paper 账户、T+1、费用、状态机 |
| `gateway/brokers/` | 连接管理、登录 assist、执行路由、live order |
| `gateway/live_trading/gates.py` | 实盘门控 Level 0–4 |
| `gateway/risk/` | Kill Switch、仓位与亏损预算 |
| `quant/application/screener_service.py` | 选股主编排 |
| `quant/screener/` | 因子、多样性、选股指南、Alpha 融合 |
| `quant/scoring/enrichment.py` | 候选 enrichment、一手计算 |
| `config/gateway.yaml` | 资金默认、安全开关 |

---

## 关键数据流

### 选股

```text
DuckDB daily_bars
  → 流动性/板块/股价过滤
  → 多因子 z-score + Alpha158-lite
  → 多样性约束 top-N
  → enrich_candidate (名称、区间、资格)
  → selection_guide + API JSON
```

### Paper 下单

```text
POST /api/v1/paper/order
  → RiskEngine 检查
  → PaperTradingEngine (T+1, lot size)
  → 持久化 paper_store
```

### 辅助实盘

```text
POST /api/v1/brokers/live-order (user_confirmed=true)
  → can_submit_live_order()
  → execution_router 选路径
  → browser_launch | qmt_csv | sidecar
  → 状态 PENDING_USER_BROKER_CONFIRM（非 FILLED）
```

---

## API 入口（常用）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/v1/system/status` | 模式、资金、门控 |
| GET | `/api/v1/screener/run` | 智能选股 |
| POST | `/api/v1/paper/start` | 启动 Paper |
| GET | `/api/v1/live-trading/gates` | 实盘门控 |
| POST | `/api/v1/brokers/live-order` | 辅助下单（dry-run 友好） |
| POST | `/api/v1/brokers/launch` | 打开券商页 |

完整列表：启动后访问 `/docs`。

---

## 安全边界（代码级）

| 开关 | 位置 | 默认 |
|------|------|------|
| `PAPER_TRADING_ONLY` | `gateway/__init__.py` | `true` |
| `real_money_execution_disabled` | `config/gateway.yaml` | 可配置 |
| `unattended_auto_enabled` | `live_trading_gates.json` | `false` |
| RBAC | `gateway/auth/rbac.py` | investor / researcher / admin |

---

## 启动与进程

```bash
# 推荐
make app
# 等价于 scripts/start-portal.sh → uvicorn gateway.api.app:app --port 8787
```

- 单进程 Uvicorn（开发/个人使用）  
- PID / 日志：`data/gateway/`  

---

## 测试金字塔

```bash
make test-gateway          # 网关冒烟
make test-core             # 就绪检查
.venv-china-quant/bin/python -m unittest discover -s tests -p 'test_*.py'
scripts/run-browser-e2e-tests.py
scripts/run_autonomous_remediation_acceptance.py
```

---

## 扩展阅读

- [gateway/01_GATEWAY_ARCHITECTURE.md](ai/gateway/01_GATEWAY_ARCHITECTURE.md)（详细审计版）  
- [MAC_BROKER_EXECUTION.md](MAC_BROKER_EXECUTION.md)  
- [audit/FUNCTION_REALITY_MATRIX.md](audit/FUNCTION_REALITY_MATRIX.md)  
