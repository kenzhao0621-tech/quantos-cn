#!/bin/bash
set -euo pipefail
cd "/Users/kenzhao/Projects/netlify-demo"
export PATH="/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin:$PATH"
/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin/python -m quant freshness-watchdog > "/Users/kenzhao/Projects/netlify-demo/docs/ai/logs/live-test-watchdog.log" 2>&1
RUN_ID=$(/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin/python -c "from quant.run_context import new_run_id; print(new_run_id())")
/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin/python -m quant fabric-fetch --datasets spot_quotes --persist --live-only --require-live >> "/Users/kenzhao/Projects/netlify-demo/docs/ai/logs/live-test-fetch.log" 2>&1 || true
/Users/kenzhao/Projects/netlify-demo/.venv-china-quant/bin/python -m quant cross-source-reconcile --dataset spot_quotes --run-id "$RUN_ID" >> "/Users/kenzhao/Projects/netlify-demo/docs/ai/logs/live-test-reconcile.log" 2>&1 || true
launchctl bootout gui/$(id -u) "/Users/kenzhao/Projects/netlify-demo/config/launchd/com.netlify-demo.quant.live-market-hours-test.plist" 2>/dev/null || true
