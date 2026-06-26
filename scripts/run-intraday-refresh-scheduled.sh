#!/usr/bin/env bash
# Scheduled intraday refresh — paths are relative to repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${ROOT}/.venv-china-quant/bin:$PATH"
SLOT="${1:-manual}"
LOG_DIR="${ROOT}/docs/ai/logs"
mkdir -p "${LOG_DIR}"

"${ROOT}/.venv-china-quant/bin/python" - <<'PY' "$SLOT" >> "${LOG_DIR}/intraday-refresh.log" 2>&1
import sys
from quant.intraday_update_scheduler import run_intraday_refresh

print(run_intraday_refresh(sys.argv[1] if len(sys.argv) > 1 else "manual"))
PY
