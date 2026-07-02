# QuantOS 2.0 风险披露（Risk Disclosure）

> 更新：2026-07-02

## 1. 本系统不是什么

- **不是投资建议**：所有评级（A/B/C/D/BLOCKED）、预期收益区间、多空理由均为研究性输出。
- **不承诺收益**：全系统（UI/报告/日志/Agent 输出）禁止且不存在"保证收益/稳赚/必涨/无风险/100% 胜率"等表述；通过历史样本外验证的策略也可能在未来亏损。
- **不做实盘自动交易**：`PAPER_TRADING_ONLY=True`、`REAL_MONEY_EXECUTION_DISABLED=True` 为模块级常量；实盘路径仅支持"生成工单 → 人工在券商端确认"（`MANUAL_CONFIRM_ONLY`），无任何直连下单 API。

## 2. 实盘权限锁

| 锁 | 位置 | 默认 |
|---|---|---|
| paper_trading_only | `gateway/config.py` L44 | true |
| real_money_execution_disabled | `gateway/config.py` L45 | true |
| enable_live_trading | `gateway/config.py` L46 | false |
| 实盘门控（法务 review + 用户确认 + 名义上限） | `gateway/live_trading/gates.py` | 全部未开启 |
| KillSwitch + 状态机 HALTED | `gateway/risk/`、`gateway/state_machine.py` | 可随时熔断 |
| RiskEngine 强制 paper_trading_only | `gateway/risk/engine.py` L145 | 拒绝任何非 paper 意图 |

未来若接入券商，必须保持默认锁关闭并要求人工二次确认（等价于重构文档要求的 `BROKER_LIVE_TRADING=false`）。

## 3. 主要风险

1. **市场风险**：A 股波动大；T+1 制度下当日买入无法当日卖出，隔夜风险不可规避。
2. **模型风险**：Kronos/因子/规则引擎均基于历史数据，市场结构变化时可能同时失效；每个建议附失效条件，触发即应停止参考。
3. **数据风险**：数据来自 AKShare/Tushare/BaoStock 公开接口，可能延迟、缺失或修正；系统对陈旧数据显式标注（stale/degraded），显示"实时已过期"时不应作为盘中决策依据。
4. **流动性与涨跌停风险**：涨停可能买不进、跌停可能卖不出；回测中已近似建模但与真实撮合存在差异。
5. **降级状态**：任何数据源/模型下载/依赖失败会自动降级并标注 `degraded`；降级输出（如 bootstrap 路径）置信度受限，不可作为决策依据。
6. **过拟合风险**：参数搜索结果附 PBO（过拟合概率）与参数敏感性；PBO 偏高或扰动即崩溃的配置会被 BLOCKED。

## 4. 用户责任

- 使用真实资金前必须自行完成尽职调查并咨询持牌顾问。
- 建议仓位遵守系统输出的单票 ≤10%、行业 ≤30% 上限，且仅投入可承受损失的资金。
- 本系统输出的 BLOCKED 结论意味着"证据不足以支持行动"，不是"反向操作信号"。
