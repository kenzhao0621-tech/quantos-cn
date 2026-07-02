# RISK_AUDIT — 风控审计

> 结论先行：风控层是本仓库最扎实的部分。纸上/影子路径有真实强制执行；实盘路径被多层门锁死为"手动确认 only"，**符合重构文档 §2.2 产品边界，全部 KEEP**。缺口在于风控与研究链路的联动（RiskManager 否决权尚未进入建议流）。

## 1. 强制执行层（KEEP）

| 组件 | 强制行为 | 证据 |
|---|---|---|
| `RiskEngine.evaluate_intent()` | kill switch、**强制 `paper_trading_only`**（false 即拒单）、模式 ∈ {PAPER, SHADOW}、数据新鲜度、日/周损失上限、单票风险、现金缓冲、100 股整手 | `gateway/risk/engine.py` L134–172 |
| 纸上引擎 | T+1 可卖数量、涨停拒买、停牌拒单，事件溯源 JSONL | `gateway/paper/engine.py` L189–258, L327 |
| KillSwitch | 持久化 halt（`kill_switch.json`），manual_reset 双确认 | `gateway/risk/kill_switch.py` L32–74 |
| 状态机 | RESEARCH_ONLY → DATA_READY → PAPER → SHADOW；live 需人工 review；任意态可 HALTED | `gateway/state_machine.py` L10–26, L72–73 |
| 数据门 | 开市时段实时快照 stale → `LIVE_SNAPSHOT_STALE` 阻断 | `gateway/data_gate.py` L107–108 |

## 2. 实盘边界（KEEP — 完全符合"禁止真实券商自动下单"）

- 默认配置：`paper_trading_only: True`、`real_money_execution_disabled: True`、`enable_live_trading: False`（`gateway/config.py` L44–46；模块常量 `gateway/__init__.py` L18）
- `can_submit_live_order()`：法务 review + 用户风险确认 + real_money_enabled + 执行级别 + 名义上限，全过才放行（`gateway/live_trading/gates.py` L106–128）
- `live_order.py` **无任何直连券商 API**：QMT 路径只落 CSV（`QMT_FILE_DROPPED`）待用户在 MiniQMT 确认；东财路径只返回操作步骤清单；终态 `PENDING_USER_BROKER_CONFIRM`；法律边界字符串 `USER_MUST_CONFIRM_ON_BROKER`（L37–111）
- `real_execution_mode: "MANUAL_CONFIRM_ONLY"`（`gateway/api/quantos.py` L27）

**重构约定**：以上边界一律不动；重构文档要求的 `BROKER_LIVE_TRADING=false` 默认锁语义已由 `real_money_execution_disabled` 实现，Phase 8 在 RISK_DISCLOSURE 文档中明示。

## 3. 缺口（进入 Phase 6/7）

| 缺口 | 说明 | 处置 |
|---|---|---|
| RiskManager 无研究链路否决权 | 风控只挡"订单"，不挡"建议"——筛选结果不经过 RiskManager 评级 | Phase 6：AgentsOS RiskManager 对每个候选输出 `must_not_trade`，可一票否决至 BLOCKED |
| 行业暴露限制未进入建议 | `quant/risk/exposure_report.py` 仅报表 | Phase 6/7 接入 PortfolioManager agent |
| position_monitor 吞异常 | `except: pass`（L24, L39），监控可能静默不完整 | Phase 1 加日志与降级标注 |
| 风险中心前端是孤儿页 | page-risk 无导航入口 | Phase 7 恢复导航并补"禁止交易原因/黑名单/数据异常/模型漂移" |
| 内存态 PnL 计数器 | RiskEngine 部分计数不持久化 | Phase 4 评估是否落盘 |
| 无黑名单机制 | 重构文档 RiskOS 要求 | Phase 6 增加符号黑名单（ST/退市整理/监管名单） |

## 4. 措辞合规

全仓（前端+后端+文档）grep 无"保证收益/稳赚/必涨/无风险/100%胜率"。免责声明存在于：首访 legal overlay（`index.html` L13–27）、帮助页、个股弹窗 footer、bucket_stats 输出（"这不是收益承诺"）。**KEEP，Phase 7 延续到新增页面与报告。**
