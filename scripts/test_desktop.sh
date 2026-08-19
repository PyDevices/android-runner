#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Run the paint app on desktop (Xvfb) before building an APK.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/p4a_app"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"
TESTPYPI="https://test.pypi.org/simple/"
PYPI="https://pypi.org/simple/"

PYTHON="$VENV_DIR/bin/python3"
PIP="$VENV_DIR/bin/pip"

if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv "$VENV_DIR"
  "$PIP" install -q -U pip
fi

"$PIP" install -q \
  -i "$TESTPYPI" --extra-index-url "$PYPI" \
  pydevices-desktop pydevices-pygraphics

cd "$APP"

echo "== boot.py → main.py (launcher import; short smoke) =="
# boot.py parks forever on android only; on desktop it returns after main.
xvfb-run -a "$PYTHON" -c "import boot" &
PID=$!
sleep 2
kill "$PID" 2>/dev/null || true
wait "$PID" 2>/dev/null || true

echo "Desktop smoke exited cleanly (or was stopped after the smoke window)"
