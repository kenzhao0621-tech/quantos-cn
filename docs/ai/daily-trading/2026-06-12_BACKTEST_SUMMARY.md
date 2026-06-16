> **⚠️ 确定性测试样本 — 非实时行情**
> - 运行模式：`FIXTURE`
> - 分析日期：2026-06-16
> - 数据提供商：fixture_bars
> - 新鲜度：HISTORICAL
> - 检索时间：2026-06-16T17:05


# 回测报告 — 601398

## 假设
- 仅做多；T+1；整手；涨跌停无法成交；含佣金与印花税；滑点配置见 config

## In-sample
```json
{
  "total_return": 0.0,
  "annualized_return": 0.0,
  "volatility": 0.0,
  "sharpe": 0,
  "sortino": 0,
  "max_drawdown": 0.0,
  "calmar": 0,
  "trade_count": 0,
  "win_rate": 0,
  "turnover": 0.0
}
```

## Out-of-sample
```json
{
  "total_return": 0.0,
  "annualized_return": 0.0,
  "volatility": 0.0,
  "sharpe": 0,
  "sortino": 0,
  "max_drawdown": 0.0,
  "calmar": 0,
  "trade_count": 0,
  "win_rate": 0,
  "turnover": 0.0
}
```

**Validation label**: PRELIMINARY

## Bias checks

- Fixture/historical only; walk-forward required for VALIDATED