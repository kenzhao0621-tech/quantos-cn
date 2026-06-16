#!/usr/bin/env bash
# make app — doctor, start portal, health poll, open browser.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv-china-quant"
PYTHON="${VENV}/bin/python"
HOST="127.0.0.1"
PORT="8787"
LOG="${ROOT}/data/gateway/app-start.log"

mkdir -p "${ROOT}/data/gateway"

{
  echo "=== QuantOS CN app start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

  if [[ ! -x "${PYTHON}" ]]; then
    echo "FAIL module=bootstrap reason=venv_missing"
    echo "FIX: make bootstrap"
    exit 1
  fi

  echo "Step: editable install"
  "${PYTHON}" -m pip install -e "${ROOT}" -q

  echo "Step: import gateway from /tmp"
  (cd /tmp && "${PYTHON}" -c "import gateway; print('import ok', gateway.__version__)")

  echo "Step: doctor"
  "${PYTHON}" -c "import gateway, quant; print('gateway', gateway.__version__)"

  echo "Step: start portal"
  bash "${ROOT}/scripts/start-portal.sh"

  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf "http://${HOST}:${PORT}/ready" >/dev/null; then
      echo "READY ok"
      break
    fi
    sleep 1
  done

  curl -sf "http://${HOST}:${PORT}/health" && echo
  curl -sf "http://${HOST}:${PORT}/ready" && echo

  echo "Portal: http://${HOST}:${PORT}/portal"
  echo "Docs:   http://${HOST}:${PORT}/docs"
  echo "Log:    ${ROOT}/data/gateway/portal.log"

  if command -v open >/dev/null 2>&1; then
    open "http://${HOST}:${PORT}/portal" || true
  fi

  echo "APP_START PASS"
} 2>&1 | tee "${LOG}"
