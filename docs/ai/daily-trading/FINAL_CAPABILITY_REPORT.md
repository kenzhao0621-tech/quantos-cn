# FINAL CAPABILITY REPORT (V4)

**Maturity**: `ACTIVE_WITH_LIMITATIONS`
**Generated**: 2026-06-16T17:48:20
**Paper trading only**: True
**Real-money execution**: disabled

## A. Executive status

- Real data path succeeded: **False**
- Quality gate: see acceptance.quality

## B. Demonstrated capabilities

- `python -m quant system-audit` — safety gates
- `python -m quant provider-check` — capability table
- `python -m quant import-snapshot` — manual CSV path
- `python -m multimodal health-check` — multimodal providers
- `npm run test:browser-policy` — 8/8 target policy tests
- Existing china_quant fixture pipeline — 23/23 tests

## C. Data coverage

- **market_snapshot**: `partial` — Composite routed snapshot; AKShare primary
- **spot_quotes**: `partial` — Public delayed A-share spot via Eastmoney/Sina
- **indices**: `partial` — Major indices (上证/深证/创业板/科创)
- **trading_calendar**: `available` — Sina trade-date history via AKShare
- **sector_boards**: `partial` — Eastmoney industry boards
- **security_master**: `partial` — A-share code/name list; Tushare if licensed
- **fundamentals**: `unavailable` — No licensed fundamental API in default install
- **institutional_flow**: `partial` — Public disclosures only via tools.china_quant
- **news**: `partial` — Web search fallback; no paywalled feeds
- **northbound_flow**: `unavailable` — Not wired in V4 default routing
- **margin_trading**: `unavailable` — Requires licensed data target

## D. Browser automation

- playwright: WORKING
- playwright_extra: OPTIONAL_PEER_NOT_INSTALLED
- stealth_lab: DISABLED_QUARANTINED
- target_policy_tests: 8/8 PASS

## E. Multimodal

- fixture_image: WORKING
- openai_cloud: NOT_CONFIGURED
- pdf_pymupdf: PARTIAL
- mcp_server: WORKING

## Acceptance

- Accepted: **False**
- Attempts logged per dataset in JSON

## F. Remaining weaknesses

- Live AKShare spot: network/provider instability (P0)
- Cloud image API: NOT_CONFIGURED — set OPENAI_API_KEY (P3)
- Docling/PaddleOCR ensemble: not wired (P2)
- 10-day paper validation not complete (P0)

## G. User action (P0)

Configure network access for AKShare or import manual snapshot:
```bash
.venv-china-quant/bin/python -m quant import-snapshot data/imports/spot_quotes_manual.csv --persist
.venv-china-quant/bin/python -m quant validate-latest-snapshot --dataset spot_quotes
```
