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
  pydevices-desktop pydevices-pygraphics pydevices-lvgl

cd "$APP"

echo "== boot.py → main.py (the launcher, for a few seconds) =="
# The launcher runs until it is closed, so the smoke stops it with timeout
# inside xvfb-run (killing xvfb-run instead orphans Python and Xvfb). A
# one-shot timer armed before boot proves multimer delivers while the
# launcher owns the main thread. The driver is a file, not -c: multimer
# decides how to keep the program alive from how it was started.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LOG="$TMP/smoke.log"
cat >"$TMP/smoke.py" <<'PY'
import os
import sys

sys.path.insert(0, os.getcwd())
import multimer

multimer.after(2000, lambda t: (print("SMOKE_TIMER", multimer.info()["source"], flush=True), multimer.report()))
import boot  # noqa: E402,F401
PY
set +e
xvfb-run -a timeout 8 "$PYTHON" "$TMP/smoke.py" >"$LOG" 2>&1
rc=$?
set -e
cat "$LOG"
if [[ $rc -ne 124 ]]; then
  echo "FAIL: the launcher exited (status $rc) before the smoke window ended" >&2
  exit 1
fi
if grep -q "Traceback" "$LOG"; then
  echo "FAIL: a traceback during the smoke" >&2
  exit 1
fi
if ! grep -q "^SMOKE_TIMER" "$LOG"; then
  echo "FAIL: the smoke timer never fired" >&2
  exit 1
fi
echo "Desktop smoke passed: the launcher ran for the whole window and a timer fired"
