# 中国A股量化交易日报 — 2026-06-16

**Decision:** `NO_TRADE`
**Run ID:** `20260617T091601-d3401222`
**Provider:** `tushare`
**Freshness:** `END_OF_DAY`
**Rows:** `5513`

## 市场状态
- Regime: `range-bound market`
- Confidence: `MEDIUM`
- Score: `0.0`

- 上证指数涨跌幅: +0.00%
- 上涨家数: 2730, 下跌家数: 2677
- 涨停约: 190, 跌停约: 9
- 指数 vs MA20: 上方

## 不交易/阻塞原因
- no name above regime threshold 80.0

## 候选池与数据审计
- 初始样本: `5513`
- Top watch: ``

## 次交易日行动清单
1. 开盘前检查实时数据 freshness 与涨跌停状态。
2. 仅在候选仍满足板块/流动性/趋势条件时进入 Paper/Shadow。
3. 若高开回落或跌破入场区，取消计划。
4. 收盘后做 T+1 验证并记录失败原因。

## 风险声明
本报告不构成投资建议。真实资金交易必须由用户本人在官方券商平台确认。