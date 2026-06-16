#!/usr/bin/env bash
# Generate Playwright visual baselines — run only when UI change is intentional.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export UPDATE_BASELINES=1
mkdir -p tests/visual/baselines docs/test-output/playwright-failures
npx playwright test tests/visual/baselines.spec.mjs
echo "Baselines written to tests/visual/baselines/"
