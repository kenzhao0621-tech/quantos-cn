# QuantOS 2.0 多智能体报告（Agent Report）

> 生成：2026-07-02 · 引擎：`deterministic_rules_v1`（TradingAgents-CN 风格架构，确定性规则实现）

## 1. 架构

9 个角色，全部**只读结构化 JSON 输入**（§7.2 契约），输出统一 JSON（§7.3 契约），不允许自由联网后编造：

```
build_agent_input(symbol)           # 真实数据：日线/行业/基本面/披露(PIT过滤)/Kronos信号/大盘状态/风险标记/回测证据
  → MarketRegimeAgent               # 大盘趋势/波动 regime
  → TechnicalAgent                  # 动量、MA、Kronos 分布信号（降级时如实标注）
  → FundamentalAgent                # PE/PB 估值
  → SentimentAgent                  # 官方披露关键词（来源+时间强制标注）
  → BullResearcher / BearResearcher # 多空辩论（各自陈列证据）
  → RiskManager                     # 一票否决：停牌/无数据/涨跌停/流动性不足 → must_not_trade
  → PortfolioManager                # 仓位上限（单票≤10%）、T+1 约束
  → FinalAdvisor                    # A/B/C/D/BLOCKED + 证据 + 失效条件 + 免责声明
```

评级语义：A=高置信研究候选（不代表一定盈利）；B=可观察候选；C=中性；D=风险过高；BLOCKED=数据不足/风控不通过/回测不通过/不可交易。

## 2. 实测样例（2026-07-02，000001.SZ 平安银行）

- **评级 B（可观察候选）**，综合 0.26 / 置信 0.56
- 看多：PE(TTM) 4.98 偏低、PB 0.46 破净、大盘 BULL_TREND
- 看空：20 日动量 -8.3%、位于 MA20 下方
- 降级智能体：SentimentAgent（无披露记录）、TechnicalAgent 中 Kronos 部分视快照可用性
- 失效条件：跌破 MA20 且动量转负 / 出现硬性风险标记 / 大盘转 BEAR_TREND / 验证门变 BLOCKED

完整 JSON 工件：`artifacts/agents/agents_000001_SZ_*.json`（含全部 9 角色输出与输入上下文）。

## 3. 诚实性设计

- RiskManager 否决为硬约束：停牌/流动性不足/无行情 → 全链 BLOCKED，PortfolioManager 不给仓位。
- 回测证据缺失（NOT_RUN）或验证门 BLOCKED 会作为风险点进入结论。
- 任一 agent 数据缺失 → `degraded: true` 逐级上传，FinalAdvisor 汇总 `degraded_agents` 并在 UI 展示"数据缺失时如实降级，不伪造结论"。
- 输出禁用词测试覆盖（保证收益/稳赚/必涨/无风险/100%胜率）。
- LLM 引擎为可选扩展位；接入后 engine 字段必须如实标注，且输入输出契约不变。

## 4. 使用

```bash
python scripts/run_agents_analysis.py --symbol 600519.SH --date latest
# 或门户「策略验证」页 → 个股多智能体研究；API: GET /api/v1/agents/analyze?symbol=600519.SH
```
