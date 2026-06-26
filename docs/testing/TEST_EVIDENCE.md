# TEST_EVIDENCE — Phase 1

> 执行时间：2026-06-17  
> 环境：macOS, Python 3.9, `.venv-china-quant`

## 命令与结果

| 命令 | 结果 | 证据 |
|---|---|---|
| `python -m unittest tests.test_phase1_infrastructure -v` | **5/5 PASS** | 见下方明细 |
| `python scripts/run-gateway-tests.py` | **PASS** (8 cases) | `docs/ai/gateway/12_TEST_READINESS.json` |
| `python scripts/run-all-readiness-tests.py` | **12/12 PASS** | SUMMARY passed=12 failed=0 |

## Phase 1 单元测试明细

```
test_error_includes_user_action_and_retryable ... ok
test_health_includes_data_gate ... ok
test_admin_starts_paper ... ok
test_viewer_gets_structured_envelope_not_exception ... ok
test_ticket_eod_returns_lines_or_actionable_blockers ... ok
```

## 合约验证（TestClient，内存 Gateway）

**Viewer Paper 启动** → HTTP 403 + 结构化 body：
- `error.code` = `PAPER_ENGINE_START_FAILED`
- `error.user_action` 存在
- `error.retryable` = true

**Admin Paper 启动** → HTTP 200, `data.status` = `PAPER_TRADING_ACTIVE`

**Health** → 含 `data_gate_verdict`, `mode`, `halted`

**票据 EOD** → `READY_FOR_MANUAL_CONFIRM` 或 `NO_EXECUTABLE_LINES` + `user_action`

## 注意事项

- 若 `:8787` 已有旧 uvicorn 进程，需 `make portal-stop && make portal` 重载代码。
- `run-app-e2e-tests.py` 回测端点可能 >30s 超时（预存问题）。

## Phase 2–8 测试（2026-06-17）

| 命令 | 结果 |
|---|---|
| `python -m unittest tests.test_phases_2_8 -v` | **11/11 PASS** |
| `python -m unittest tests.test_phase1_infrastructure tests.test_phases_2_8 -v` | **16/16 PASS** |

覆盖：MarketDataGateway、多样性约束、新手 onboarding、DSR/PBO、Paper Engine、BrokerGateway、Live 门控、新 API 端点。

## Lint / Typecheck

- 本项目 Python 包无 mypy CI 门禁；Phase 1 改动文件无新增 linter 报错。
- 前端为原生 JS，无 TypeScript typecheck。

## Build

- QuantOS 无前端 build 步骤；`make bootstrap` + editable install 为等效 build。
- `package.json` Netlify 脚本与 QuantOS Gateway 独立，Phase 1 未改动。
