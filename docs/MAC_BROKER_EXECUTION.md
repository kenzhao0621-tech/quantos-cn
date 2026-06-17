# Mac 券商多路径无人值守执行架构

## 设计原则

一条路径失败，自动尝试下一条，直到成功或全部耗尽。

## 路径优先级

| 优先级 | path_id | Mac 无人值守 | 说明 |
|--------|---------|-------------|------|
| 1 | `remote_sidecar` | **是** | Mac → HTTP → Windows VM `broker_sidecar_server.py` → MiniQMT xtquant API |
| 2 | `xtquant_local` | **是** | 仅 Windows 本机 MiniQMT |
| 3 | `playwright_auto` | **条件** | 已保存浏览器会话 + 门控 `CONDITIONAL_AUTO` + 可选 `browser_auto_submit` |
| 4 | `qmt_csv_drop` | **是** | 订单 CSV 写入 QMT 监控目录 |
| 5 | `playwright_assist` | 否 | 预填，人工点确认 |
| 6 | `browser_launch` | 否 | 仅打开官方 URL |

## Mac 推荐：Sidecar（真·无人值守 API 下单）

```bash
# Windows VM 内（MiniQMT 已登录）:
python scripts/broker_sidecar_server.py --host 0.0.0.0 --port 8799 \
  --miniqmt-path "C:\国金证券QMT交易端\userdata_mini" --account YOUR_ACCOUNT

# Mac 隧道（可选）:
bash scripts/mac_broker_tunnel.sh user@windows-host

# Portal 券商页填写 Sidecar URL: http://127.0.0.1:8799
```

## 门控（须全部满足才无人值守）

- `execution_level` >= 3 (`CONDITIONAL_AUTO`)
- `unattended_auto_enabled` = true
- `real_money_enabled` = true
- `user_confirmed_risk` = true
- `legal_review_passed` = true（若 `legal_review_required`）
- 单笔/日限额内

## API

- `GET /api/v1/brokers/execution-paths` — 探测各路径可用性
- `POST /api/v1/brokers/execute-auto` — 无人值守多路径下单
- `POST /api/v1/brokers/live-order` — `unattended: true` 同上

## 浏览器券商（华泰/同花顺/中信等）

- 登录：`POST /api/v1/brokers/login-assist`
- 自选：`POST /api/v1/watchlist/sync`
- 无人值守：需 `browser_auto_submit` + 已保存会话（稳定性低于 Sidecar）

## 验证状态

- 单元测试：`tests/test_execution_router.py`
- Sidecar 客户端：`tests/test_remote_sidecar.py`
- 链式测试：`scripts/run-broker-live-chain-test.py`
- **需你手动验证**：Windows VM Sidecar 真实发单、各券商 Playwright 自动提交
