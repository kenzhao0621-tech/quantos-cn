#!/usr/bin/env bash
# SSH tunnel: Mac localhost:8799 -> Windows VM broker sidecar
# Usage: bash scripts/mac_broker_tunnel.sh user@192.168.64.2

set -euo pipefail
REMOTE="${1:-}"
LOCAL_PORT="${LOCAL_PORT:-8799}"
REMOTE_PORT="${REMOTE_PORT:-8799}"

if [[ -z "$REMOTE" ]]; then
  echo "用法: bash scripts/mac_broker_tunnel.sh user@windows-vm-ip"
  echo "然后在 Gateway 券商页设置 Sidecar URL: http://127.0.0.1:${LOCAL_PORT}"
  exit 1
fi

echo "隧道: 127.0.0.1:${LOCAL_PORT} -> ${REMOTE}:${REMOTE_PORT}"
echo "保持此终端开启。另开终端运行 make portal"
exec ssh -N -L "${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" "$REMOTE"
