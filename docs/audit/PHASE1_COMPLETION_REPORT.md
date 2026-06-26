# Phase 1 Completion Report

## 1. 本阶段目标

修复基础设施：Paper 启动可诊断、票据生成可解释、统一错误与 trace、健康检查、开发环境可验证。

## 2. 根因和现状

| 问题 | 根因 | Phase 1 处理 |
|---|---|---|
| Paper 启动失败 | viewer 缺 `mode:promote`；UI 未门控 | 结构化 `PAPER_ENGINE_START_FAILED`；前端 `applyPermissionGates()` |
| 票据「失败」 | `NO_EXECUTABLE_LINES`（资金 vs 高价股） | `user_action` + 资金约束 blockers |
| 错误不可操作 | envelope 仅 code/message | 增加 `user_action`, `retryable`, `details` |
| 健康检查过简 | `/health` 仅 version | 增加 mode、data_gate_verdict、halted |

## 3. 修改文件

- `gateway/api/envelope.py`
- `gateway/api/operations.py`
- `gateway/api/app.py`
- `gateway/autopilot.py`
- `apps/portal-web/app.js`
- `apps/portal-web/api-client.js`
- `tests/test_phase1_infrastructure.py`
- `tests/__init__.py`
- `docs/audit/FUNCTION_REALITY_MATRIX.md`（新建）
- `docs/audit/MIGRATION_PLAN.md`（新建）
- `docs/testing/TEST_EVIDENCE.md`（新建）
- `docs/ai/PROJECT_STATE.md`（更新）

## 4. 数据库变更

无。继续使用 DuckDB + JSON 文件存储。

## 5. API 变更

| 端点 | 变更 |
|---|---|
| `POST /api/v1/paper/start` | 403/401 返回结构化 envelope（非裸 detail）；成功含 request_id/trace_id |
| `GET /health` | 新增 `mode`, `halted`, `data_gate_verdict`, safety flags |
| `POST /api/v1/autopilot/order-ticket` | `NO_EXECUTABLE_LINES` 时响应含 `user_action`, `retryable`, `affordability` |

## 6. 前端变更

- 登录后缓存 `permissions`；无 `mode:promote` 时禁用 Paper/Shadow 按钮
- Toast 优先显示 `error.user_action`
- 票据空行显示 `user_action` 提示

## 7. 算法变更

无。

## 8. 风控变更

无逻辑变更；Paper 启动前仍检查 kill switch 与状态机。

## 9. 测试

- 新增 `tests/test_phase1_infrastructure.py`（5 cases）
- 回归 `scripts/run-gateway-tests.py`
- 回归 `scripts/run-all-readiness-tests.py`

## 10. 测试结果

| 套件 | 结果 |
|---|---|
| Phase 1 unittest | **5/5 PASS** |
| Gateway tests | **8/8 PASS** |
| Readiness | **12/12 PASS** |

证据：`docs/testing/TEST_EVIDENCE.md`

## 11. 尚未解决

- 运行中 uvicorn 需重启才加载新 `/health` 与 paper 错误格式
- 无独立 Paper Engine / worker 队列
- 实时行情 provider 未配置
- `run-app-e2e-tests.py` 回测超时（>30s）
- 券商 Gateway 仍为 handoff 模式

## 12. 风险

- 403 + JSON envelope 与旧客户端仅读 `detail` 的兼容性 — 门户已更新
- 权限门控可能使 viewer 困惑 — title 提示所需权限

## 13. 回滚方式

```bash
git checkout -- gateway/api/envelope.py gateway/api/operations.py gateway/api/app.py
git checkout -- gateway/autopilot.py apps/portal-web/app.js apps/portal-web/api-client.js
rm tests/test_phase1_infrastructure.py
make portal-stop && make portal
```

## 14. 下一阶段

**Phase 2**：MarketDataGateway、REALTIME/DELAYED/EOD 标签、选股价格预算与多样性约束、数据质量门控。
