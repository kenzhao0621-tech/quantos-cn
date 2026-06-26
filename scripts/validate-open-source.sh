#!/usr/bin/env bash
# Pre-push check: no local absolute paths or secrets in tracked source.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

FAIL=0

echo "=== QuantOS CN open-source validation ==="

if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "FAIL: .env is tracked by git"
  FAIL=1
fi

# User home paths (not URL path segments like /home/index.html)
if git grep -E '/Users/[A-Za-z]|C:\\\\Users\\\\' -- gateway quant apps integrations config configs tests Makefile pyproject.toml .env.example 2>/dev/null | head -1 | grep -q .; then
  echo "FAIL: absolute user path in source:"
  git grep -n -E '/Users/[A-Za-z]|C:\\\\Users\\\\' -- gateway quant apps integrations config configs tests Makefile pyproject.toml .env.example 2>/dev/null | head -8
  FAIL=1
fi

if git grep -E '[a-zA-Z0-9._%+-]+@(gmail|qq)\.com' -- gateway quant apps integrations scripts config configs tests 2>/dev/null | grep -v validate-open-source | head -1 | grep -q .; then
  echo "FAIL: email-like pattern in source:"
  git grep -n -E '[a-zA-Z0-9._%+-]+@(gmail|qq)\.com' -- gateway quant apps integrations scripts config configs tests 2>/dev/null | grep -v validate-open-source | head -5
  FAIL=1
fi

TRACKED_RUNTIME=(
  memory/documents/fts.sqlite
  docs/ai/gateway/audit/events.jsonl
  docs/ai/daily-trading/PAPER_SIGNAL_LEDGER.jsonl
  config/launchd/com.netlify-demo.quant.daily-report.plist
)

for f in "${TRACKED_RUNTIME[@]}"; do
  if git ls-files --error-unmatch "${f}" >/dev/null 2>&1; then
    echo "FAIL: runtime/local file tracked: ${f}"
    FAIL=1
  fi
done

if [[ "${FAIL}" -eq 0 ]]; then
  echo "PASS: source tree looks safe for open-source publish"
  exit 0
fi

echo "FIX issues above before pushing to GitHub"
exit 1
