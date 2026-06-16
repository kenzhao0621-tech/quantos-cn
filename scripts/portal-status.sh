#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="${ROOT}/data/gateway/portal.pid"
HOST="127.0.0.1"
PORT="8787"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "RUNNING pid=$(cat "${PID_FILE}") url=http://${HOST}:${PORT}/portal"
else
  echo "STOPPED"
fi

if curl -sf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
  echo "HEALTH ok"
  curl -sf "http://${HOST}:${PORT}/ready" | head -c 200 || true
  echo
else
  echo "HEALTH fail"
fi
