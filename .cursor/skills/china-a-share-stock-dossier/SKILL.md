---
name: china-a-share-stock-dossier
description: >-
  Generate complete Chinese stock analysis dossiers for primary candidates.
  Use with china-a-share-daily-trading-outlook. Implementation in
  tools/china_quant/dossier.py. PAPER_TRADING_ONLY.
---

# Stock Dossier

```bash
python3 tools/china_quant/cli.py stock-dossier --code 601398 --fixture universe_full
```

Output: `docs/ai/daily-trading/YYYY-MM-DD_PRIMARY_CANDIDATES/CODE.md`

Spec: `docs/china-a-share-intelligence/11_STOCK_DOSSIER_SPEC.md`
