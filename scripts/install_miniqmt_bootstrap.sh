#!/usr/bin/env bash
# MiniQMT / xtquant bootstrap for macOS gateway host.
# MiniQMT CLIENT is Windows-only — this script prepares Python side + runs acceptance.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ROOT}/.venv-china-quant/bin/python"
PIP="${ROOT}/.venv-china-quant/bin/pip"

echo "== QuantOS Broker Bootstrap =="
echo "Platform: $(uname -s)"

if [[ "$(uname -s)" != "Darwin" && "$(uname -s)" != "Linux" ]]; then
  echo "For native MiniQMT install on Windows, run: scripts/install_miniqmt_windows.ps1"
fi

echo ">> Installing xtquant Python package (SDK stub)..."
"$PIP" install -q xtquant 2>/dev/null || echo "xtquant pip install skipped or failed"

echo ">> Probing xtquant runtime..."
"$VENV" "$ROOT/scripts/broker_xtquant_probe.py" || true

echo ">> Running multi-broker capability acceptance..."
"$VENV" "$ROOT/scripts/broker_capability_acceptance.py" || true

echo ""
echo "== MiniQMT 真实连接说明 =="
echo "1. macOS 无法原生安装 MiniQMT 客户端（仅 Windows）"
echo "2. 请用 Parallels/UTM 安装 Windows，在虚拟机内："
echo "   - 向券商（国金/华泰/中信等）申请 QMT/MiniQMT"
echo "   - 安装后以「极简模式」登录"
echo "   - QMT 设置 → 下载 Python 库 → 复制 xtquant 到 Python"
echo "3. 本机 Gateway 已支持 9 家浏览器券商（涨乐/同花顺/君弘等）立即可用"
echo "4. 验收报告: data/gateway/broker_capability_acceptance.json"
echo ""
echo "== Mac 真实自动交易（远程 Sidecar）=="
echo "1. Windows VM: python scripts/broker_sidecar_server.py --miniqmt-path ... --account ..."
echo "2. Mac 隧道: bash scripts/mac_broker_tunnel.sh user@vm-ip"
echo "3. Gateway 券商页 Sidecar URL: http://127.0.0.1:8799"
echo "4. 选择「Mac · 远程 Sidecar」并测试 Sidecar 连接"
