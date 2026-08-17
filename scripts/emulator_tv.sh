#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Install the p4a_app APK on a running Android TV / Fire TV emulator and launch
# via the leanback activity.
#
# Why a separate script: phone emulator.sh assumes a phone AVD; TV images use
# android-tv system images and should be started with LEANBACK in mind.
#
# Usage:
#   ./scripts/emulator_tv.sh [APK_PATH]
#
# Environment: same as scripts/emulator.sh (ANDROID_HOME, ADB, PACKAGE_ID, …)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Why: reuse phone install/launch plumbing; document TV AVD setup below.
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Install the APK on a connected Android TV / Fire TV emulator and launch it.

  ./scripts/emulator_tv.sh [APK_PATH]

Create a TV AVD (example, API 34 x86_64):

  sdkmanager "system-images;android-34;android-tv;x86_64"
  avdmanager create avd -n pydevices_examples_tv_api34 -k \
    "system-images;android-34;android-tv;x86_64" -d "tv_1080p"
  emulator -avd pydevices_examples_tv_api34 &

Then re-run this script. Leanback intent is in p4a_app/intent_filters_tv.xml.
For a landscape 10-foot framebuffer, import board_config_tv in main.py before
paint (sets PYDEVICES_WIDTH/HEIGHT), then rebuild.
EOF
  exit 0
fi

echo "==> Android TV / Fire OS smoke (leanback packaging)"
echo "    Tip: use an android-tv system image AVD; see --help for create steps."
exec "$ROOT/scripts/emulator.sh" "$@"
