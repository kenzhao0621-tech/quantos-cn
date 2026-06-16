---
name: china-market-rules-engine
description: >-
  China A-share trading rules — T+1, price limits, boards (主板/科创/创业板/北交所),
  ST, suspensions, lot size. Use before any entry recommendation. PRIMARY for rules;
  called by china-a-share-daily-trading-outlook. Do NOT recommend impossible entries.
---

# China Market Rules Engine

Implementation: `tools/china_quant/rules.py`

## Check before entry

- 停牌、涨停买不到、跌停难卖出
- ST 默认回避（除非用户明确要求）
- 新股历史不足
- T+1 卖出约束说明

```python
from tools.china_quant.rules import check_entry_feasible, t_plus_one_note
```

## Boards

主板 ±10%，科创/创业板 ±20%，北交所 ±30%，ST ±5%（简化模型，以交易所最新规则为准）
