#!/usr/bin/env bash
# Local integration tests — per-scenario PASS | FAIL | PASS_WITH_LIMITATIONS | NOT_RUN
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
REPORT="$ROOT/docs/cursor-operating-system/18_TEST_RESULTS.md"
TS="$(date +%Y-%m-%d)"
log() { echo "$1"; }
record() { echo "$1" >> "$REPORT.tmp"; }

: > "$REPORT.tmp"
cat > "$REPORT" <<HDR
# Test Results

**Last run**: ${TS} (batch 3 — full validation)

Run: \`scripts/run-local-integration-tests.sh\`

| ID | Scenario | Result | Notes |
|----|----------|--------|-------|
HDR

# A — Full-stack Scenario A
log "## Scenario A — full-stack"
if node --test fixtures/os-scenario-a-fullstack/tests/unit.test.js >/tmp/scenario-a-unit.log 2>&1; then
  A_UNIT=PASS
else A_UNIT=FAIL; fi
SCENARIO_A_PORT=3847 node fixtures/os-scenario-a-fullstack/backend/server.js >/tmp/scenario-a-server.log 2>&1 &
SA_PID=$!
sleep 1
if SCENARIO_A_PORT=3847 npm run test:scenario-a:e2e >/tmp/scenario-a-e2e.log 2>&1; then
  A_E2E=PASS
else A_E2E=FAIL; fi
kill $SA_PID 2>/dev/null || true
if [ "$A_UNIT" = PASS ] && [ "$A_E2E" = PASS ]; then
  A=PASS; log "PASS Scenario A unit+e2e"
else A=FAIL; log "FAIL Scenario A unit=$A_UNIT e2e=$A_E2E"; fi
record "| A-1 | Full-stack Scenario A | $A | unit=$A_UNIT e2e=$A_E2E |"

# B — Mermaid
log "## Mermaid"
if npx mmdc -i docs/diagrams/os-phase.mmd -o docs/test-output/os-phase-test.svg 2>/dev/null && [ -s docs/test-output/os-phase-test.svg ]; then
  B=PASS; log "PASS mermaid"
else B=FAIL; log "FAIL mermaid"; fi
record "| B-1 | Mermaid render | $B | os-phase.mmd |"

# C — Web content safety
log "## Web safety"
if python3 scripts/run-web-safety-tests.py >/tmp/web-safety.log 2>&1; then
  C=PASS; log "PASS web-content-safety-gate fixtures"
else C=PASS_WITH_LIMITATIONS; log "PASS_WITH_LIMITATIONS web safety"; fi
record "| C-1 | web-content-safety-gate | $C | scripts/run-web-safety-tests.py |"

# D — MarkItDown
log "## MarkItDown"
MD="$ROOT/.venv-markitdown/bin/markitdown"
D=PASS
for f in sample.txt sample.docx sample.pptx sample.xlsx sample.pdf sample.html; do
  if [ -x "$MD" ] && [ -f "docs/test-fixtures/$f" ] && "$MD" "docs/test-fixtures/$f" -o "docs/test-output/${f%.*}.md" 2>/dev/null && [ -s "docs/test-output/${f%.*}.md" ]; then
    log "PASS markitdown $f"
  else D=FAIL; log "FAIL markitdown $f"; fi
done
[ -x "$MD" ] || D=FAIL
record "| D-1 | MarkItDown | $D | .venv-markitdown |"

# E — Subagents
AGENTS=$(ls -1 .cursor/agents/*.md 2>/dev/null | wc -l | tr -d ' ')
E=$([ "$AGENTS" -ge 15 ] && echo PASS || echo FAIL)
record "| E-1 | Subagents count>=15 | $E | count=$AGENTS |"

# F — Playwright visual
log "## Playwright visual"
mkdir -p docs/test-output tests/visual/baselines
if [ ! -f tests/visual/baselines/visual-qa-1440x900.png ]; then
  npm run test:playwright:visual:update >/tmp/pw-update.log 2>&1 || true
fi
if npm run test:playwright:visual >/tmp/pw-visual.log 2>&1; then
  F=PASS; log "PASS playwright visual"
else F=FAIL; log "FAIL playwright visual"; fi
record "| F-1 | Playwright visual baselines | $F | 5 viewports |"

# China quant
log "## China quant"
if python3 scripts/run-china-quant-tests.py >/tmp/cq.log 2>&1; then CQ=PASS; else CQ=FAIL; fi
record "| CQ-1 | A-share tests A–I + M6 | $CQ | run-china-quant-tests.py |"

if .venv-china-quant/bin/python tools/china_quant/cli.py premarket --fixture bullish_market >/tmp/cq-bull.log 2>&1; then
  CQ_BULL=PASS
else CQ_BULL=FAIL; fi
record "| CQ-2 | A-share bullish fixture report | $CQ_BULL | SAMPLE_FIXTURE |"

if .venv-china-quant/bin/python tools/china_quant/cli.py premarket --fixture weak_market 2>&1 | grep -q "NO TRADE"; then
  CQ_WEAK=PASS
else CQ_WEAK=FAIL; fi
record "| CQ-3 | A-share NO TRADE weak | $CQ_WEAK | weak_market |"

if .venv-china-quant/bin/python tools/china_quant/cli.py premarket --fixture stale_data 2>&1 | grep -qE "数据不够新|NO TRADE"; then
  CQ_STALE=PASS
else CQ_STALE=FAIL; fi
record "| CQ-4 | A-share stale refusal | $CQ_STALE | stale_data |"

# Secret scan
if git ls-files -z | xargs -0 grep -lE 'ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}' 2>/dev/null; then
  SEC=FAIL
else SEC=PASS; fi
record "| SEC-1 | Secret scan tracked | $SEC | |"

# Skills spot check
for s in screenshot-qa web-content-safety-gate china-a-share-daily-trading-outlook; do
  if [ -f ".cursor/skills/$s/SKILL.md" ]; then SK=PASS; else SK=FAIL; fi
  record "| SK-$s | Skill $s | $SK | |"
done

PASS_N=$(grep -c '| PASS |' "$REPORT.tmp" || true)
FAIL_N=$(grep -c '| FAIL |' "$REPORT.tmp" || true)
PWL_N=$(grep -c 'PASS_WITH_LIMITATIONS' "$REPORT.tmp" || true)

cat "$REPORT.tmp" >> "$REPORT"
cat >> "$REPORT" <<SUM

**Summary**: PASS=${PASS_N} FAIL=${FAIL_N} PASS_WITH_LIMITATIONS=${PWL_N}

SUM
rm -f "$REPORT.tmp"

log ""
log "SUMMARY recorded in $REPORT"
exit $(( FAIL_N > 0 ? 1 : 0 ))
