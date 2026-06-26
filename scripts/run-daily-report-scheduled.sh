#!/usr/bin/env bash
# Scheduled daily quant report — paths are relative to repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${ROOT}/.venv-china-quant/bin:$PATH"
PYTHON="${ROOT}/.venv-china-quant/bin/python"
LOG_DIR="${ROOT}/docs/ai/logs"
mkdir -p "${LOG_DIR}" "${ROOT}/data/gateway"

"${PYTHON}" -c "from quant.daily_report_scheduler import is_trading_day_today; import sys; sys.exit(0 if is_trading_day_today() else 0)"

"${PYTHON}" "${ROOT}/scripts/run-daily-quant-pipeline.py" >> "${LOG_DIR}/daily-report.log" 2>&1
