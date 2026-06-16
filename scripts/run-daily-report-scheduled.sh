#!/bin/bash
set -euo pipefail
cd "/Users/kenzhao/Projects/netlify-demo"
export PATH="/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin:$PATH"
/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin/python -c "from quant.daily_report_scheduler import is_trading_day_today; import sys; sys.exit(0 if is_trading_day_today() else 0)" 
/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin/python - <<'PY'
from quant.daily_report_scheduler import is_trading_day_today
import sys
if not is_trading_day_today():
    print("NON_TRADING_DAY — skip daily report")
    sys.exit(0)
PY
LOCK="/Users/kenzhao/Projects/netlify-demo/data/gateway/daily_report.lock"
if [ -f "$LOCK" ]; then echo "duplicate run blocked"; exit 0; fi
touch "$LOCK"
trap 'rm -f "$LOCK"' EXIT
/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin/python "/Users/kenzhao/Projects/netlify-demo/scripts/run-daily-quant-pipeline.py" >> "/Users/kenzhao/Projects/netlify-demo/docs/ai/logs/daily-report.log" 2>&1
