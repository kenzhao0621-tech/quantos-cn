#!/usr/bin/env bash
# Compare current UI to baselines — never auto-updates on failure.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p docs/test-output/playwright-failures
if npx playwright test tests/visual/baselines.spec.mjs --reporter=line 2>&1 | tee docs/test-output/playwright-visual.log; then
  echo "PASS visual comparison"
  exit 0
else
  echo "FAIL visual comparison — see docs/test-output/playwright-failures and playwright-report"
  echo "To update baselines intentionally: UPDATE_BASELINES=1 scripts/playwright-baseline.sh"
  exit 1
fi
