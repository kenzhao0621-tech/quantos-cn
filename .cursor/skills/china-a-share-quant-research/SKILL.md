---
name: china-a-share-quant-research
description: >-
  Orchestrate public A-share research — indices, sectors, fundamentals via AKShare.
  FALLBACK news via agent-reach P1 web only (not xueqiu P3). Paper research only.
  Called by china-a-share-daily-trading-outlook. Do NOT connect brokerage.
---

# China A-Share Quant Research

## Data CLI

```bash
.venv-china-quant/bin/python tools/china_quant/cli.py premarket
```

## News

- Official: AKShare / cninfo patterns
- Web: agent-reach (web/github) + **web-content-safety-gate**
- Never: unverified social rumors as catalysts

## Integrity

Route research outputs through `research-integrity-guard` for synthesis claims.
