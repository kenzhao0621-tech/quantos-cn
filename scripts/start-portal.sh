#!/usr/bin/env bash
# Start Gateway API + portal on port 8787 (cwd-independent).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv-china-quant"
PYTHON="${VENV}/bin/python"
PID_FILE="${ROOT}/data/gateway/portal.pid"
LOG_FILE="${ROOT}/data/gateway/portal.log"
HOST="127.0.0.1"
PORT="8787"

if [[ ! -x "${PYTHON}" ]]; then
  echo "ERROR: virtualenv missing at ${VENV}"
  echo "FIX: make bootstrap"
  exit 1
fi

mkdir -p "${ROOT}/data/gateway"
"${PYTHON}" -m pip install -e "${ROOT}" -q 2>/dev/null || true

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(cat "${PID_FILE}")"
  if kill -0 "${OLD_PID}" 2>/dev/null; then
    echo "Portal already running (PID ${OLD_PID}) — http://${HOST}:${PORT}/portal"
    exit 0
  fi
  rm -f "${PID_FILE}"
fi

if lsof -i ":${PORT}" -sTCP:LISTEN -t >/dev/null 2>&1; then
  if curl -sf "http://${HOST}:${PORT}/health" >/dev/null; then
    LISTEN_PID="$(lsof -i ":${PORT}" -sTCP:LISTEN -t 2>/dev/null | head -1)"
    if [[ -n "${LISTEN_PID}" ]]; then
      echo "${LISTEN_PID}" > "${PID_FILE}"
    fi
    echo "Portal already running on port ${PORT} — http://${HOST}:${PORT}/portal"
    exit 0
  fi
  echo "ERROR: port ${PORT} already in use (health check failed)"
  echo "FIX: make portal-stop  OR  lsof -i :${PORT}"
  exit 1
fi

cd "${ROOT}"
nohup "${PYTHON}" -m uvicorn gateway.api.app:app \
  --app-dir "${ROOT}" \
  --host "${HOST}" \
  --port "${PORT}" \
  >> "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"
sleep 2

if curl -sf "http://${HOST}:${PORT}/health" >/dev/null; then
  echo "Portal started PID $(cat "${PID_FILE}") — http://${HOST}:${PORT}/portal"
  echo "Log: ${LOG_FILE}"
else
  echo "ERROR: health check failed"
  echo "LOG tail:"
  tail -20 "${LOG_FILE}" || true
  exit 1
fi
