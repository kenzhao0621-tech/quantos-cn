#!/bin/bash
set -euo pipefail
cd "/Users/kenzhao/Projects/netlify-demo"
export PATH="/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin:$PATH"
SLOT="${1:-scheduled}"
"/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin/python" - <<'PY' "$SLOT" >> "/Users/kenzhao/Projects/netlify-demo/docs/ai/logs/intraday-refresh.log" 2>&1
import sys
from quant.intraday_update_scheduler import run_intraday_refresh
print(run_intraday_refresh(sys.argv[1]))
PY
