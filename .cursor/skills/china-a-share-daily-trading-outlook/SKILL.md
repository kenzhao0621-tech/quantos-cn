---
name: china-a-share-daily-trading-outlook
description: >-
  PRIMARY entry for daily China A-share market outlook, sector ranking, and
  paper-trading stock plans in plain Chinese. Use for A股、大盘、板块、今日买什么、
  止损止盈、盘前简报、复盘. PAPER_TRADING_ONLY — never auto-orders. Outputs
  NO TRADE when appropriate. Calls china-market-rules-engine, china-quant-data-quality-guard,
  china-equity-risk-model, research-integrity-guard. Do NOT duplicate trading-agents
  (QUARANTINE) or promise returns.
disable-model-invocation: false
---

# A股每日交易作战简报（PRIMARY）

## 原则

- **资本保全优先于交易频率**；`NO TRADE` / 观望是成功输出
- 初学者友好：白话中文，解释为何、何时失效、最大可接受亏损
- **仅研究与模拟**，用户本人决定真实下单
- 不承诺收益、不捏造内幕、不把传闻当事实

## 工作流

### 盘前（Pre-market）

1. `china-quant-data-quality-guard` — 交易日历、数据时效
2. 拉取数据：`.venv-china-quant` + AKShare（失败则用 fixture 并标注 BLOCKED_BY_DATA）
3. `china-market-rules-engine` — T+1、涨跌停、停牌
4. 大盘 regime → 板块排序 → 个股筛选 → `china-a-share-factor-lab` 100分制
5. `china-equity-risk-model` — 止损、止盈、仓位（单票 10–20% 上限）
6. `research-integrity-guard` + 公告/新闻 integrity
7. 生成中文报告 → `docs/ai/daily-trading/YYYY-MM-DD_PREMARKET.md`

```bash
.venv-china-quant/bin/python tools/china_quant/cli.py premarket
# fixture: ... premarket --fixture weak_market
```

### 盘中（仅用户请求）

- 必须标注：当前时间、数据时间、REAL_TIME/DELAYED/PREVIOUS_CLOSE
- 数据不够新 → `Data is not current enough for a live entry decision.`

### 盘后

- 复盘 → `YYYY-MM-DD_POSTMARKET.md`；更新 `PERFORMANCE_LEDGER.csv`
- **禁止**事后改写盘前原文

## 输出上限

- 首选：0–3
- 观察名单：0–5
- 评分：首选 ≥75，观察 ≥65

## 报告模板

见 `references/report-template-zh.md`

## 负向触发

- 真实下单、券商密码、代客理财承诺
- 使用 trading-agents 实盘模块
- 数据陈旧仍给盘中建议

## 状态

`ACTIVE_WITH_LIMITATIONS` — 需 AKShare；Tushare 可选
