#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Install the pydevices-examples demo APK on a USB-connected Android phone and debug via logcat.
#
# Usage:
#   ./scripts/phone.sh [APK_PATH]
#   ./scripts/phone.sh --no-logs [APK_PATH]
#
# Environment:
#   ANDROID_HOME          Android SDK (default: ~/.buildozer/android/platform/android-sdk)
#   ADB                   Override adb executable (auto-detected on WSL vs Linux)
#   ANDROID_SERIAL        Target a specific phone when multiple are connected
#   PACKAGE_ID            App id (default: org.pydevices.launcher)
#   ACTIVITY              Main activity (default: org.kivy.android.PythonActivity)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/p4a_app"

PACKAGE_ID="${PACKAGE_ID:-org.pydevices.launcher}"
ACTIVITY="${ACTIVITY:-org.kivy.android.PythonActivity}"
COMPONENT="${PACKAGE_ID}/${ACTIVITY}"

ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/.buildozer/android/platform/android-sdk}}"

NO_LOGS=0
APK_ARG=""

is_wsl() {
  if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
    return 0
  fi
  if [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    return 0
  fi
  return 1
}

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \?//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --no-logs) NO_LOGS=1; shift ;;
    *)
      if [[ -n "$APK_ARG" ]]; then
        echo "Unexpected argument: $1" >&2
        usage 1
      fi
      APK_ARG="$1"
      shift
      ;;
  esac
done

print_missing_phone_wsl() {
  cat <<'EOF'

No USB Android phone is connected to adb (or the device is unauthorized).

On WSL, the phone is usually plugged into Windows and adb runs via adb.exe:

  1. On the phone: Settings → About phone → tap Build number 7 times (enable Developer options)
  2. Settings → Developer options → enable USB debugging
  3. Connect USB; on the phone tap Allow when prompted for this computer
  4. On Windows, install Android Studio or platform-tools if needed
  5. From WSL, confirm the phone is visible:
       adb.exe devices
     Expect a serial (not emulator-5554) and state "device"

If adb.exe is missing, add Windows platform-tools to PATH:
  export PATH="$PATH:/mnt/c/Users/$USER/AppData/Local/Android/Sdk/platform-tools"

Or set ADB explicitly:
  ADB='/mnt/c/Users/YOUR_USER/AppData/Local/Android/Sdk/platform-tools/adb.exe' ./scripts/phone.sh

If the phone shows "unauthorized", unlock it and accept the RSA fingerprint prompt, then re-run.

If adb.exe sees the phone on Windows but WSL adb does not, use adb.exe (this script tries that on WSL).

Build the APK first if needed:
  ./build_android.sh
EOF
}

print_missing_phone_unix() {
  cat <<EOF

No USB Android phone is connected to adb (or the device is unauthorized).

  1. On the phone: enable Developer options and USB debugging
  2. Connect USB; accept the RSA fingerprint prompt on the phone
  3. Linux udev (Debian/Ubuntu example):
       sudo apt install android-sdk-platform-tools
       # optional udev rules if device not listed — see Android developer docs
  4. Confirm:
       adb devices
     Expect your phone serial and state "device" (not "unauthorized")

  5. Re-run:
       ./scripts/phone.sh

Build the APK first if needed:
  ./build_android.sh
EOF
}

pick_adb() {
  if [[ -n "${ADB:-}" ]]; then
    echo "$ADB"
    return 0
  fi

  if is_wsl; then
    if command -v adb.exe >/dev/null 2>&1; then
      echo "adb.exe"
      return 0
    fi
    local win_adb
    for win_adb in \
      "/mnt/c/Users/${USER}/AppData/Local/Android/Sdk/platform-tools/adb.exe" \
      "/mnt/c/Users/${WSL_USER:-}/AppData/Local/Android/Sdk/platform-tools/adb.exe"; do
      if [[ -x "$win_adb" ]]; then
        echo "$win_adb"
        return 0
      fi
    done
  fi

  local candidates=(
    "$ANDROID_HOME/platform-tools/adb"
    "${ANDROID_SDK_ROOT:-}/platform-tools/adb"
    "$HOME/Android/Sdk/platform-tools/adb"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  if command -v adb >/dev/null 2>&1; then
    echo "adb"
    return 0
  fi

  return 1
}

find_apk() {
  local arg="${1:-}"
  if [[ -n "$arg" ]]; then
    if [[ -f "$arg" ]]; then
      echo "$(cd "$(dirname "$arg")" && pwd)/$(basename "$arg")"
      return 0
    fi
    echo "APK not found: $arg" >&2
    return 1
  fi

  local -a candidates=()
  local dir apk
  for dir in "$APP/bin"; do
    [[ -d "$dir" ]] || continue
    shopt -s nullglob
    for apk in "$dir"/*.apk; do
      candidates+=("$apk")
    done
    shopt -u nullglob
  done

  if [[ ${#candidates[@]} -eq 0 ]]; then
    echo "No APK found. Build one first:" >&2
    echo "  cd $ROOT && ./build_android.sh" >&2
    return 1
  fi

  local newest="${candidates[0]}"
  local path
  for path in "${candidates[@]}"; do
    if [[ "$path" -nt "$newest" ]]; then
      newest="$path"
    fi
  done
  echo "$(cd "$(dirname "$newest")" && pwd)/$(basename "$newest")"
}

adb_cmd() {
  # Windows adb.exe invoked from WSL often ignores ANDROID_SERIAL; pass -s explicitly.
  if [[ -n "${ANDROID_SERIAL:-}" ]]; then
    "$ADB_BIN" -s "$ANDROID_SERIAL" "$@"
  else
    "$ADB_BIN" "$@"
  fi
}

adb_install_arg() {
  local apk=$1
  if is_wsl && [[ "$ADB_BIN" == *adb.exe || "$ADB_BIN" == adb.exe ]]; then
    wslpath -w "$apk"
  else
    echo "$apk"
  fi
}

list_physical_devices() {
  # adb.exe prints CRLF; strip \r so $2 matches "device"
  adb_cmd devices | tr -d '\r' | awk '
    NR > 1 && $1 !~ /^emulator-/ {
      if ($2 == "device") print $1
    }
  '
}

list_blocked_devices() {
  adb_cmd devices | tr -d '\r' | awk '
    NR > 1 && $1 !~ /^emulator-/ && ($2 == "unauthorized" || $2 == "offline") {
      print $1, $2
    }
  '
}

ADB_BIN="$(pick_adb)" || {
  echo "adb not found." >&2
  if is_wsl; then
    print_missing_phone_wsl
  else
    print_missing_phone_unix
  fi
  exit 1
}

APK_PATH="$(find_apk "$APK_ARG")"

if is_wsl; then
  echo "==> WSL detected — using adb: $ADB_BIN"
else
  echo "==> Linux/macOS — using adb: $ADB_BIN"
fi
echo "==> APK: $APK_PATH"

BLOCKED="$(list_blocked_devices || true)"
if [[ -n "$BLOCKED" ]]; then
  echo "==> Phone connected but not ready:" >&2
  echo "$BLOCKED" >&2
  if is_wsl; then
    print_missing_phone_wsl
  else
    print_missing_phone_unix
  fi
  exit 1
fi

mapfile -t PHONES < <(list_physical_devices)
if [[ ${#PHONES[@]} -eq 0 ]]; then
  echo "==> No USB phone connected (emulators are ignored; use ./scripts/emulator.sh)." >&2
  if is_wsl; then
    print_missing_phone_wsl
  else
    print_missing_phone_unix
  fi
  exit 1
fi

if [[ -n "${ANDROID_SERIAL:-}" ]]; then
  echo "==> Using ANDROID_SERIAL=$ANDROID_SERIAL"
elif [[ ${#PHONES[@]} -gt 1 ]]; then
  echo "==> Multiple phones connected; using ${PHONES[0]}"
  echo "    Set ANDROID_SERIAL to pick another: ${PHONES[*]}"
  export ANDROID_SERIAL="${PHONES[0]}"
else
  export ANDROID_SERIAL="${PHONES[0]}"
fi

echo "==> Phone serial: $ANDROID_SERIAL"

INSTALL_PATH="$(adb_install_arg "$APK_PATH")"
echo "==> Installing on $ANDROID_SERIAL"
adb_cmd install -r "$INSTALL_PATH"

echo "==> Launching $COMPONENT"
adb_cmd shell am start -n "$COMPONENT"

echo "==> Demo launched on $ANDROID_SERIAL"
if [[ "$NO_LOGS" == "1" ]]; then
  echo "    View logs: $ADB_BIN logcat -s python:V SDL:V ActivityManager:I"
  exit 0
fi

echo "==> logcat (python / SDL / ActivityManager — Ctrl+C to stop)"
adb_cmd logcat -c
adb_cmd logcat -s python:V SDL:V ActivityManager:I
