# Alert Templates (manual / future automation)

Every alert MUST include: stock, condition, current time, data time, suggested action, risk warning.

## Entry trigger

```
【入场提醒】{name} ({code})
条件：{entry_confirm}
当前时间：{now}
数据时间：{data_time}
建议：{action}
风险：本提醒仅为研究参考，非自动下单。止损 {stop}。
```

## Stop-loss

```
【止损提醒】{name} ({code})
条件：价格触及 {stop}
当前时间：{now}
建议：按原计划止损或减仓，勿扩大亏损。
```

## Regime change

```
【市场状态变化】
原状态：{old_regime} → 新状态：{new_regime}
当前时间：{now}
建议：{guidance}
```

## Data stale

```
【数据不可用】
Data is not current enough for a live entry decision.
数据时间：{data_time}
建议：暂停盘中新开仓，等待数据更新。
```

Prevent duplicate alerts for the same condition on the same day.
