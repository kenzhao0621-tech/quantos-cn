#!/usr/bin/env bash
# Live market hours acceptance harness — paths relative to repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${ROOT}/.venv-china-quant/bin:$PATH"
PYTHON="${ROOT}/.venv-china-quant/bin/python"
LOG_DIR="${ROOT}/data/gateway/logs"
mkdir -p "${LOG_DIR}"

"${PYTHON}" -m quant freshness-watchdog > "${LOG_DIR}/live-test-watchdog.log" 2>&1 &
RUN_ID=$("${PYTHON}" -c "from quant.run_context import new_run_id; print(new_run_id())")
"${PYTHON}" -m quant fabric-fetch --datasets spot_quotes --persist --live-only --require-live >> "${LOG_DIR}/live-test-fetch.log" 2>&1 || true
"${PYTHON}" -m quant cross-source-reconcile --dataset spot_quotes --run-id "${RUN_ID}" >> "${LOG_DIR}/live-test-reconcile.log" 2>&1 || true

PLIST="${ROOT}/config/launchd/com.netlify-demo.quant.live-market-hours-test.plist"
if [[ -f "${PLIST}" ]] && command -v launchctl >/dev/null 2>&1; then
  launchctl bootout "gui/$(id -u)" "${PLIST}" 2>/dev/null || true
fi
