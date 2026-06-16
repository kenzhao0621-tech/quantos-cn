# A股每日交易工作流

**模式**: `PAPER_TRADING_ONLY` — 仅研究与模拟，不会自动下单。

## 目录

| 文件 | 说明 |
|------|------|
| `YYYY-MM-DD_PREMARKET.md` | 盘前作战简报 |
| `YYYY-MM-DD_POSTMARKET.md` | 盘后复盘（不修改盘前原文） |
| `PERFORMANCE_LEDGER.csv` | 绩效账本（含失败与 NO TRADE） |
| `DATA_SOURCE_LEDGER.md` | 数据来源记录 |
| `MODEL_LIMITATIONS.md` | 模型与数据局限 |
| `RISK_CONTROL_POLICY.md` | 风控政策 |
| `NOTIFICATION_TEMPLATES.md` | 提醒模板（手动） |

## 命令

```bash
.venv-china-quant/bin/python tools/china_quant/cli.py premarket --fixture bullish_market
.venv-china-quant/bin/python tools/china_quant/cli.py premarket --fixture weak_market
.venv-china-quant/bin/python tools/china_quant/cli.py premarket --fixture stale_data
.venv-china-quant/bin/python tools/china_quant/cli.py postmarket --fixture bullish_market
```

## 原则

- `NO TRADE` 是成功输出
- 样本 fixture 明确标注，不冒充实时行情
- 账本保留亏损与观望记录，禁止事后改写盘前预测
