#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="${ROOT}/data/gateway/portal.pid"
PORT="8787"

stop_pid() {
  local pid="$1"
  if kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    sleep 1
    kill -9 "${pid}" 2>/dev/null || true
    echo "Stopped PID ${pid}"
  fi
}

if [[ -f "${PID_FILE}" ]]; then
  stop_pid "$(cat "${PID_FILE}")"
  rm -f "${PID_FILE}"
fi

for pid in $(lsof -i ":${PORT}" -sTCP:LISTEN -t 2>/dev/null || true); do
  stop_pid "${pid}"
done

echo "Portal stopped (port ${PORT})"
