---
name: china-a-share-factor-lab
description: >-
  Transparent 100-point scoring for A-share candidates (regime, sector, trend,
  liquidity, fundamentals, valuation, catalyst, risk). Use with china-a-share-daily-trading-outlook.
  Thresholds — primary ≥75, watchlist ≥65. High score does not guarantee return.
---

# Factor Lab

`tools/china_quant/scoring.py`

| Component | Max points |
|-----------|------------|
| Market regime fit | 15 |
| Sector strength | 15 |
| Trend & momentum | 20 |
| Volume & liquidity | 10 |
| Fundamental quality | 15 |
| Valuation context | 10 |
| Confirmed catalysts | 10 |
| Risk control | 5 |

Deductions: overheated, weak liquidity, rumors, poor R:R.

Signal validation labels: VALIDATED | PRELIMINARY | UNVALIDATED | FAILED
