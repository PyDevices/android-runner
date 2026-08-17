#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Optional helper: rewrite user main.py to import an alternate module.
# Packaged p4a entry is boot.py; main.py is the MicroPython-style user entry.
#
# Usage:
#   ./scripts/install_apk_main.sh DEST_DIR
#
# Environment:
#   APK_ENTRY   Module name to import (default: paint). Set to "skip" to no-op.
set -euo pipefail

DEST="${1:-}"
if [[ -z "$DEST" ]]; then
  echo "Usage: $0 DEST_DIR" >&2
  exit 1
fi

ENTRY="${APK_ENTRY:-paint}"
if [[ "$ENTRY" == "skip" ]]; then
  exit 0
fi

# Strip optional .py suffix
ENTRY="${ENTRY%.py}"

if [[ ! -f "$DEST/${ENTRY}.py" ]]; then
  echo "APK entry module not found: $DEST/${ENTRY}.py" >&2
  exit 1
fi

cat > "$DEST/main.py" <<PY
# SPDX-License-Identifier: MIT
# User entry (boot.py is the p4a source.main). Rewritten by install_apk_main.sh.
import utils.path  # noqa: F401
import ${ENTRY}
PY

echo "==> Wrote $DEST/main.py -> import utils.path; import ${ENTRY}"
