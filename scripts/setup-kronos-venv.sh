#!/usr/bin/env bash
# KronosOS sidecar environment — Python 3.10+ required by Kronos (main venv is 3.9).
# Any failure leaves a degraded status file; the main app keeps working.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv-kronos"
VENDOR="$ROOT/vendor/kronos"
STATUS_DIR="$ROOT/data/quantos"
STATUS="$STATUS_DIR/kronos_status.json"
mkdir -p "$STATUS_DIR" "$ROOT/vendor"

fail() {
  echo "{\"installed\": false, \"degraded\": true, \"reason\": \"$1\", \"checked_at\": \"$(date -Iseconds)\"}" > "$STATUS"
  echo "KRONOS SETUP DEGRADED: $1"
  exit 1
}

PY=""
for cand in python3.12 python3.11 python3.10; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
[ -n "$PY" ] || fail "python3.10+_not_found"

if [ ! -x "$VENV/bin/python" ]; then
  "$PY" -m venv "$VENV" || fail "venv_create_failed"
fi

"$VENV/bin/pip" install --quiet --upgrade pip || fail "pip_upgrade_failed"
"$VENV/bin/pip" install --quiet torch numpy pandas huggingface_hub einops matplotlib tqdm safetensors || fail "deps_install_failed"

if [ ! -d "$VENDOR/.git" ]; then
  git clone --depth 1 https://github.com/shiyu-coder/Kronos.git "$VENDOR" || fail "kronos_clone_failed"
fi

# Pre-download Kronos-mini weights + 2k tokenizer.
"$VENV/bin/python" - <<'EOF' || fail "model_download_failed"
from huggingface_hub import snapshot_download
for repo in ("NeoQuasar/Kronos-mini", "NeoQuasar/Kronos-Tokenizer-2k"):
    snapshot_download(repo_id=repo)
    print("downloaded", repo)
EOF

# Smoke import inside sidecar env.
"$VENV/bin/python" - <<EOF || fail "kronos_import_failed"
import sys
sys.path.insert(0, "$VENDOR")
from model import Kronos, KronosTokenizer, KronosPredictor  # noqa
import torch
print("kronos import ok, torch", torch.__version__)
EOF

cat > "$STATUS" <<EOF
{"installed": true, "degraded": false, "model": "kronos-mini", "tokenizer": "Kronos-Tokenizer-2k",
 "venv": ".venv-kronos", "vendor": "vendor/kronos", "checked_at": "$(date -Iseconds)"}
EOF
echo "KRONOS SETUP OK"
