#!/usr/bin/env bash
# Create isolated native venvs for vn.py and Qlib — does NOT modify .venv-china-quant
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY312="/opt/homebrew/opt/python@3.12/libexec/bin/python"
if [[ ! -x "$PY312" ]]; then
  PY312="$(command -v python3.12 || true)"
fi
if [[ ! -x "$PY312" ]]; then
  echo "ERROR: Python 3.12 required for native vn.py 4.x"
  exit 1
fi

echo "Using $PY312 ($("$PY312" --version))"

# vn.py native venv
VNVPY="$ROOT/.venv-vnpy-native"
if [[ ! -d "$VNVPY" ]]; then
  "$PY312" -m venv "$VNVPY"
fi
"$VNVPY/bin/pip" install -U pip wheel setuptools -q
"$VNVPY/bin/pip" install vnpy -q
echo "vnpy native: $($VNVPY/bin/python -c 'import vnpy; print(vnpy.__version__)')"

# Qlib native venv
VQLIB="$ROOT/.venv-qlib-native"
if [[ ! -d "$VQLIB" ]]; then
  "$PY312" -m venv "$VQLIB"
fi
"$VQLIB/bin/pip" install -U pip wheel setuptools -q
"$VQLIB/bin/pip" install pyqlib lightgbm numpy pandas duckdb pyarrow scikit-learn -q
echo "qlib native: $($VQLIB/bin/python -c 'import qlib; print(qlib.__version__)')"

echo "Native venvs ready:"
echo "  $VNVPY"
echo "  $VQLIB"
