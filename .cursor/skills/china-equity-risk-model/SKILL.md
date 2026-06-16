---
name: china-equity-risk-model
description: >-
  Stop-loss, profit-taking, position sizing (10–20% single name cap), and confidence
  levels (HIGH/MEDIUM/LOW/NO TRADE) for A-shares. Required for every primary candidate.
  Called by china-a-share-daily-trading-outlook.
---

# Equity Risk Model

## Every primary candidate MUST have

- Stop price + % loss + invalidation reason
- Target1 / Target2 partial exit zones
- Cancel entry conditions
- Position cap: 10–20% of trading capital (percent if account unknown)

## Confidence

| Level | When |
|-------|------|
| HIGH | Strong data, regime, sector, setup, liquidity, R:R |
| MEDIUM | Partial uncertainty |
| LOW | Watchlist only |
| NO TRADE | Stale data, excessive risk, no setup |

Never widen stop to avoid loss recognition.

## Sizing formula

```
max_loss_amount / (entry - stop) per share → shares (round to 100-share lots)
```

See `tools/china_quant/rules.py` LOT_SIZE = 100.
