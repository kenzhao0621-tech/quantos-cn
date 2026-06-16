---
name: china-a-share-event-study
description: >-
  Evaluate official announcements and exchange disclosures as catalysts for A-shares.
  Reject rumors. Use with research-integrity-guard. Called before scoring catalyst points.
---

# Event Study

`tools/china_quant/news_integrity.py`

## Before using news as catalyst

1. Prefer official company / exchange announcements
2. Verify publication time
3. Check if market already priced in
4. Separate fact vs media interpretation
5. Reject unattributed rumors

```python
from tools.china_quant.news_integrity import assess_catalyst
```

Social-media-only → **not usable as catalyst**.
