# Portal failure root cause

- Generated: 2026-06-16T15:16:03.211192Z
- Base URL: http://127.0.0.1:8787
- Buttons tested: 32
- Success: 28
- Failed: 3

## Failures by classification

### API_BUSINESS_FAILURE (1)

- **paper** / 启动 Paper (`paper-start`) — selector `#page-paper button[data-action="paper-start"]`
  - network: [{'phase': 'response', 'method': 'POST', 'url': 'http://127.0.0.1:8787/api/v1/paper/start', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/shadow/status', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/research/reports', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/risk/status', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/system/status', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/paper/positions', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/native/status', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/paper/orders', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/paper/pnl', 'status': 200}]
  - screenshot: `docs/ai/final/screenshots/portal-audit/paper_paper-start.png`

### FRONTEND_EVENT_NOT_BOUND (1)

- **overview** / 更新数据 (`market-update`) — selector `#page-overview button[data-action="market-update"]`
  - screenshot: `docs/ai/final/screenshots/portal-audit/overview_market-update.png`

### UI_NO_FEEDBACK (1)

- **paper** / 刷新状态 (`paper-refresh`) — selector `#page-paper button[data-action="paper-refresh"]`
  - network: [{'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/paper/positions', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/paper/orders', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/paper/pnl', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/risk/status', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/shadow/status', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/research/reports', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/system/status', 'status': 200}, {'phase': 'response', 'method': 'GET', 'url': 'http://127.0.0.1:8787/api/v1/native/status', 'status': 200}]
  - screenshot: `docs/ai/final/screenshots/portal-audit/paper_paper-refresh.png`
