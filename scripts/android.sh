#!/usr/bin/env bash
# Stage a host .py (cwd path) onto the PyDevices Android launcher via adb and
# relaunch. Lives in pydevices-android-template/scripts/ (symlink from ~/bin/android.sh).
# CLI shape matches unix micropython (-c / -m / file / -i / -X …).
# Path resolution matches CLI python — NOT pyscript.sh gallery lookup.
#
# Usage (from e.g. pydevices-examples/lib, with ~/bin on PATH):
#   android.sh examples/lv_test_timer.py
#   android.sh -c 'print(1+1)'
#   android.sh -m lv_test_timer
#   android.sh -i
#   android.sh examples/foo.py -i
#   android.sh --clear
#
# Environment:
#   ADB                   Override adb executable
#   ANDROID_SERIAL        Device serial (-s for adb.exe)
#   PACKAGE_ID            Default org.pydevices.launcher
#   ACTIVITY              Default org.kivy.android.PythonActivity
#   ANDROID_STDIO_PORT    Default 18765 (must match app stdio_sidecar)
#   PYDEVICES_EXAMPLES_ROOT        Sibling pydevices-examples checkout (examples / tools)
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# scripts/ → pydevices-android-template/
ANDROID_ROOT="$(cd "$_SCRIPT_DIR/.." && pwd)"
# Prefer sibling pydevices-examples next to this repo (examples, tools, packages).
if [[ -z "${PYDEVICES_EXAMPLES_ROOT:-}" ]]; then
  if [[ -d "$ANDROID_ROOT/../pydevices-examples/lib" ]]; then
    PYDEVICES_EXAMPLES_ROOT="$(cd "$ANDROID_ROOT/../pydevices-examples" && pwd)"
  else
    PYDEVICES_EXAMPLES_ROOT=""
  fi
fi

PACKAGE_ID="${PACKAGE_ID:-org.pydevices.launcher}"
ACTIVITY="${ACTIVITY:-org.kivy.android.PythonActivity}"
COMPONENT="${PACKAGE_ID}/${ACTIVITY}"
STDIO_PORT="${ANDROID_STDIO_PORT:-18765}"

FILE_ARG=""
MODULE_ARG=""
CMD_ARG=""
CLEAR=0
LOGCAT=0
KIT=0
HOLD_S=""
DEPS_ARG=""
MODULES_ARG=""
MANIFESTS_ARG=""
REPL=0
NO_ATTACH=0
VERBOSE=0
OPTIMIZE=""
X_OPTS=()
SHOW_VERSION=0

usage() {
  cat <<EOF
usage: android.sh [<opts>] [-X <implopt>] [-c <command> | -m <module> | <filename>]
Options:
--version : show version information
-h : print this help message
-i : enable inspection via REPL after running command/module/file
-v : verbose (host staging / attach); can be multiple
-O[N] : accepted for micropython CLI parity (no-op on Android CPython)

Implementation specific options (-X):
  compile-only                 -- accepted (no-op on Android CPython)
  emit={bytecode,native,viper} -- accepted (no-op on Android CPython)
  heapsize=<n>[w][K|M]         -- accepted (no-op on Android CPython)

Android / pydevices-examples extras:
  --repl            same as -i
  --no-attach       launch only; do not wire this terminal to app stdio
  --clear           restore packaged launcher main.py; clear run/
  --logcat          follow python/SDL logcat after start (or alone)
  --kit             write run_argv with "kit" for example_test_kit
  --hold-s SEC      keep presenting for SEC after oneshot entry returns
  --deps A,B        companion staging notes
  --modules A,B     push src/examples/<name>.py beside entry when found
  --manifests A,B   push packages/<name>.json when found under repo

When stdin is a TTY, stays attached (app stdin/stdout/stderr in this terminal).
Ctrl-\\\\ disconnects attach. Path resolution matches CLI python — not pyscript gallery.

Environment:
  ADB  ANDROID_SERIAL  PACKAGE_ID  ACTIVITY  PYDEVICES_EXAMPLES_ROOT  ANDROID_STDIO_PORT
  (PYDEVICES_EXAMPLES_ROOT defaults to sibling ../pydevices-examples from this repo)
EOF
}

logv() {
  if [[ "$VERBOSE" -gt 0 ]]; then
    echo "android.sh: $*" >&2
  fi
}

is_wsl() {
  if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
    return 0
  fi
  if [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
    return 0
  fi
  return 1
}

pick_adb() {
  if [[ -n "${ADB:-}" ]]; then
    echo "$ADB"
    return 0
  fi
  if is_wsl && command -v adb.exe >/dev/null 2>&1; then
    echo "adb.exe"
    return 0
  fi
  local candidates=(
    "${ANDROID_HOME:-}/platform-tools/adb"
    "${ANDROID_SDK_ROOT:-}/platform-tools/adb"
    "$HOME/Android/Sdk/platform-tools/adb"
    "$HOME/.buildozer/android/platform/android-sdk/platform-tools/adb"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
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

adb_cmd() {
  if [[ -n "${ANDROID_SERIAL:-}" ]]; then
    "$ADB_BIN" -s "$ANDROID_SERIAL" "$@"
  else
    "$ADB_BIN" "$@"
  fi
}

list_devices() {
  adb_cmd devices | tr -d '\r' | awk 'NR>1 && $2=="device" { print $1 }'
}

require_device() {
  mapfile -t DEVICES < <(list_devices)
  if [[ ${#DEVICES[@]} -eq 0 ]]; then
    echo "android.sh: no adb device connected" >&2
    echo "  Start an emulator (or plug in a phone), then re-run." >&2
    exit 1
  fi
  if [[ -z "${ANDROID_SERIAL:-}" && ${#DEVICES[@]} -gt 1 ]]; then
    export ANDROID_SERIAL="${DEVICES[0]}"
    echo "android.sh: multiple devices; using $ANDROID_SERIAL" >&2
  elif [[ -z "${ANDROID_SERIAL:-}" ]]; then
    export ANDROID_SERIAL="${DEVICES[0]}"
  fi
}

require_package() {
  if ! adb_cmd shell pm path "$PACKAGE_ID" 2>/dev/null | tr -d '\r' | grep -q .; then
    echo "android.sh: package not installed: $PACKAGE_ID" >&2
    echo "  Build/install: cd $ANDROID_ROOT && ./build_android.sh -y && ./scripts/emulator.sh" >&2
    exit 1
  fi
}

run_as() {
  adb_cmd shell "run-as $PACKAGE_ID sh -c $(printf '%q' "$*")"
}

# Push host file to /data/local/tmp then copy into app files (direct push often fails).
stage_file() {
  local host_path=$1
  local dest_rel=$2
  local base
  base="$(basename "$host_path")"
  local tmp="/data/local/tmp/pydevices-examples-android-$base"
  adb_cmd push "$host_path" "$tmp" >/dev/null
  adb_cmd shell "run-as $PACKAGE_ID sh -c 'mkdir -p files/app/$(dirname "$dest_rel"); cp $tmp files/app/$dest_rel'"
}

write_app_file() {
  local dest_rel=$1
  local content=$2
  local tmp
  tmp="$(mktemp)"
  printf '%s\n' "$content" >"$tmp"
  stage_file "$tmp" "$dest_rel"
  rm -f "$tmp"
}

# p4a may leave legacy .pyc that shadows updated bootstrap / helpers.
purge_stale_bytecode() {
  adb_cmd shell "run-as $PACKAGE_ID sh -c 'rm -f files/app/boot.pyc files/app/main.pyc files/app/stdio_sidecar.pyc files/app/mp_*.pyc; rm -rf files/app/__pycache__/boot.* files/app/__pycache__/main.* files/app/__pycache__/stdio_sidecar.* files/app/__pycache__/mp_*'" >/dev/null 2>&1 || true
}

android_app_dir() {
  local app="$ANDROID_ROOT/p4a_app"
  [[ -f "$app/boot.py" && -f "$app/stdio_sidecar.py" ]] || return 1
  printf '%s\n' "$app"
}

# Hot-sync boot + stdio helpers (never overwrite staged user main.py).
sync_bootstrap() {
  local app
  app="$(android_app_dir)" || return 0
  stage_file "$app/boot.py" "boot.py"
  stage_file "$app/stdio_sidecar.py" "stdio_sidecar.py"
  # MicroPython-parity REPL helpers (history / tab / help / continue).
  local helper
  for helper in mp_readline.py mp_complete.py mp_continue.py mp_help.py; do
    if [[ -f "$app/$helper" ]]; then
      stage_file "$app/$helper" "$helper"
    fi
  done
  purge_stale_bytecode
  echo "android.sh: synced boot.py + stdio_sidecar + mp_*.py from $ANDROID_ROOT" >&2
}

restore_launcher_main() {
  local app
  app="$(android_app_dir)" || {
    echo "android.sh: cannot restore main.py (missing $ANDROID_ROOT/p4a_app)" >&2
    return 1
  }
  stage_file "$app/main.py" "main.py"
  echo "android.sh: restored launcher main.py" >&2
}

# User entry: MicroPython-style main.py that imports the staged run/ module.
write_user_main() {
  local mod=$1
  write_app_file "main.py" "import ${mod}"
  # Drop legacy run_entry so boot.py prefers main.py.
  adb_cmd shell "run-as $PACKAGE_ID sh -c 'rm -f files/app/run_entry'" >/dev/null 2>&1 || true
}

relaunch() {
  sync_bootstrap
  purge_stale_bytecode
  adb_cmd shell am force-stop "$PACKAGE_ID" >/dev/null || true
  adb_cmd shell am start -n "$COMPONENT" >/dev/null
  echo "android.sh: launched $COMPONENT"
}

do_clear() {
  adb_cmd shell "run-as $PACKAGE_ID sh -c 'rm -rf files/app/run files/app/run_entry files/app/run_argv'"
  restore_launcher_main || true
  echo "android.sh: cleared staged run/; restored launcher main.py"
  relaunch
}

do_logcat() {
  adb_cmd logcat -c || true
  exec adb_cmd logcat -v time python:V SDL:V AndroidRuntime:E '*:S'
}

app_is_running() {
  adb_cmd shell pidof "$PACKAGE_ID" 2>/dev/null | tr -d '\r' | grep -q .
}

ensure_app_started() {
  # Soft start — do not force-stop (keeps a live REPL/stdio session).
  if app_is_running; then
    purge_stale_bytecode
    return 0
  fi
  sync_bootstrap
  purge_stale_bytecode
  adb_cmd shell am start -n "$COMPONENT" >/dev/null
  echo "android.sh: started $COMPONENT"
}

should_attach() {
  if [[ "$NO_ATTACH" -eq 1 ]]; then
    return 1
  fi
  if [[ "$LOGCAT" -eq 1 && "$REPL" -eq 0 ]]; then
    # Explicit logcat follow replaces stdio attach for this invocation.
    return 1
  fi
  [[ -t 0 ]]
}

attach_stdio() {
  local mode=$1
  echo "android.sh: attaching terminal (MODE=$mode, port $STDIO_PORT)" >&2
  adb_cmd forward "tcp:${STDIO_PORT}" "tcp:${STDIO_PORT}" >/dev/null
  local attach_py="$_SCRIPT_DIR/android_stdio_attach.py"
  if [[ ! -f "$attach_py" ]]; then
    echo "android.sh: missing $attach_py" >&2
    return 1
  fi
  # Prefer python3 on WSL; fall back to python.
  local py=python3
  if ! command -v python3 >/dev/null 2>&1; then
    py=python
  fi
  "$py" "$attach_py" --port "$STDIO_PORT" --mode "$mode" || {
    local rc=$?
    adb_cmd forward --remove "tcp:${STDIO_PORT}" >/dev/null 2>&1 || true
    return "$rc"
  }
  adb_cmd forward --remove "tcp:${STDIO_PORT}" >/dev/null 2>&1 || true
}

stage_optional_csv() {
  local kind=$1
  local csv=$2
  [[ -n "$csv" ]] || return 0
  local IFS=','
  local name
  for name in $csv; do
    name="$(echo "$name" | tr -d '[:space:]')"
    [[ -n "$name" ]] || continue
    case "$kind" in
      modules)
        if [[ -f "$PYDEVICES_EXAMPLES_ROOT/src/examples/${name}.py" ]]; then
          stage_file "$PYDEVICES_EXAMPLES_ROOT/src/examples/${name}.py" "run/${name}.py"
          echo "android.sh: staged module $name"
        else
          echo "android.sh: warning: module not found: $name" >&2
        fi
        ;;
      manifests)
        if [[ -f "$PYDEVICES_EXAMPLES_ROOT/packages/${name}.json" ]]; then
          stage_file "$PYDEVICES_EXAMPLES_ROOT/packages/${name}.json" "run/${name}.json"
          echo "android.sh: staged manifest $name"
        else
          echo "android.sh: warning: manifest not found: $name" >&2
        fi
        ;;
      deps)
        # Dep names are for documentation / future on-device pip; core stack is baked.
        echo "android.sh: note: --deps $name (baked APK should already provide it)" >&2
        ;;
    esac
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --version)
      SHOW_VERSION=1
      shift
      ;;
    -v)
      VERBOSE=$((VERBOSE + 1))
      shift
      ;;
    -O|-O[0-9]*)
      OPTIMIZE="${1#-O}"
      [[ -n "$OPTIMIZE" ]] || OPTIMIZE=1
      shift
      ;;
    -X)
      [[ $# -ge 2 ]] || {
        echo "android.sh: -X requires an implopt" >&2
        exit 1
      }
      case "$2" in
        compile-only|emit=bytecode|emit=native|emit=viper|heapsize=*)
          X_OPTS+=("$2")
          ;;
        *)
          echo "android.sh: unknown -X option: $2" >&2
          echo "Invalid command line arguments. Use -h option for help." >&2
          exit 1
          ;;
      esac
      shift 2
      ;;
    -c)
      CMD_ARG="${2?}"
      [[ -n "$CMD_ARG" ]] || {
        echo "android.sh: -c requires a command" >&2
        exit 1
      }
      shift 2
      ;;
    --clear)
      CLEAR=1
      shift
      ;;
    --logcat)
      LOGCAT=1
      shift
      ;;
    -i|--repl)
      REPL=1
      shift
      ;;
    --no-attach)
      NO_ATTACH=1
      shift
      ;;
    --kit)
      KIT=1
      shift
      ;;
    --hold-s)
      HOLD_S="${2:?--hold-s requires seconds}"
      shift 2
      ;;
    -m)
      MODULE_ARG="${2:?-m requires a module name}"
      shift 2
      ;;
    --deps)
      DEPS_ARG="${2:?--deps requires a value}"
      shift 2
      ;;
    --modules)
      MODULES_ARG="${2:?--modules requires a value}"
      shift 2
      ;;
    --manifests)
      MANIFESTS_ARG="${2:?--manifests requires a value}"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "android.sh: unknown option: $1" >&2
      echo "Invalid command line arguments. Use -h option for help." >&2
      exit 1
      ;;
    *)
      if [[ -n "$FILE_ARG" ]]; then
        echo "android.sh: unexpected argument: $1" >&2
        exit 1
      fi
      FILE_ARG=$1
      shift
      ;;
  esac
done

# Mutual exclusion like micropython: -c | -m | <filename>
n_entry=0
[[ -n "$FILE_ARG" ]] && n_entry=$((n_entry + 1))
[[ -n "$MODULE_ARG" ]] && n_entry=$((n_entry + 1))
[[ -n "$CMD_ARG" ]] && n_entry=$((n_entry + 1))
if [[ "$n_entry" -gt 1 ]]; then
  echo "android.sh: use only one of -c, -m, or <filename>" >&2
  exit 1
fi

if [[ "$SHOW_VERSION" -eq 1 ]]; then
  echo "PyDevices android.sh (host wrapper for ${PACKAGE_ID})"
  if ADB_BIN="$(pick_adb 2>/dev/null)"; then
    if adb_cmd shell pm path "$PACKAGE_ID" >/dev/null 2>&1; then
      ver="$(adb_cmd shell dumpsys package "$PACKAGE_ID" 2>/dev/null | tr -d '\r' | sed -n 's/^ *versionName=//p' | head -1 || true)"
      if [[ -n "$ver" ]]; then
        echo "Installed APK versionName=${ver}"
      fi
    fi
  fi
  if [[ -n "$OPTIMIZE" ]]; then
    logv "-O${OPTIMIZE} ignored on Android CPython"
  fi
  exit 0
fi

ADB_BIN="$(pick_adb)" || {
  echo "android.sh: adb not found (on WSL install platform-tools and use adb.exe)" >&2
  exit 1
}
if is_wsl || [[ "$VERBOSE" -gt 0 ]]; then
  echo "android.sh: using adb: $ADB_BIN" >&2
fi
if [[ -n "$OPTIMIZE" ]]; then
  logv "-O${OPTIMIZE} accepted (no-op on Android CPython)"
fi
if [[ "${#X_OPTS[@]}" -gt 0 ]]; then
  logv "-X opts: ${X_OPTS[*]}"
fi

require_device
require_package

if [[ "$CLEAR" -eq 1 ]]; then
  do_clear
  if [[ "$LOGCAT" -eq 1 ]]; then
    do_logcat
  fi
  if should_attach; then
    if [[ "$REPL" -eq 1 ]]; then
      attach_stdio repl
    else
      attach_stdio stdio
    fi
  fi
  exit 0
fi

if [[ -z "$FILE_ARG" && -z "$MODULE_ARG" && -z "$CMD_ARG" ]]; then
  if [[ "$LOGCAT" -eq 1 && "$REPL" -eq 0 ]]; then
    do_logcat
  fi
  if [[ "$REPL" -eq 1 ]]; then
    # Bare ``-i``: omit main.py (MicroPython: no main → REPL). Clear staged run/.
    adb_cmd shell "run-as $PACKAGE_ID sh -c 'rm -rf files/app/run files/app/run_entry files/app/run_argv files/app/main.py files/app/main.pyc files/app/__pycache__/main.*'" >/dev/null 2>&1 || true
    relaunch
  else
    # Bare invoke: relaunch current entry (launcher or last staged main.py).
    relaunch
  fi
  if should_attach; then
    if [[ "$REPL" -eq 1 ]]; then
      attach_stdio repl
    else
      attach_stdio stdio
    fi
  fi
  exit 0
fi

ENTRY_NAME=""

if [[ -n "$CMD_ARG" ]]; then
  # micropython/python -c: exec command as main, sys.argv[0] == '-c'
  cmd_tmp="$(mktemp)"
  python3 - "$CMD_ARG" "$cmd_tmp" <<'PY'
import pathlib
import sys

cmd = sys.argv[1]
path = pathlib.Path(sys.argv[2])
path.write_text(
    "import sys\n"
    "sys.argv[0] = '-c'\n"
    "exec(compile(%r, '<string>', 'exec'))\n" % (cmd,),
    encoding="utf-8",
)
PY
  adb_cmd shell "run-as $PACKAGE_ID sh -c 'rm -rf files/app/run; mkdir -p files/app/run'"
  stage_file "$cmd_tmp" "run/_android_c.py"
  rm -f "$cmd_tmp"
  ENTRY_NAME="_android_c"
  echo "android.sh: staged -c command -> run/_android_c.py"
  logv "command: $CMD_ARG"
elif [[ -n "$FILE_ARG" ]]; then
  if [[ "$FILE_ARG" = /* ]]; then
    RESOLVED="$FILE_ARG"
  else
    RESOLVED="$(pwd)/$FILE_ARG"
  fi
  if [[ ! -e "$RESOLVED" ]]; then
    echo "android.sh: file not found: $FILE_ARG (cwd=$(pwd))" >&2
    exit 1
  fi
  if [[ -d "$RESOLVED" ]]; then
    echo "android.sh: '$FILE_ARG' is a directory; pass a .py file or use -m" >&2
    exit 1
  fi
  STEM="$(basename "$RESOLVED")"
  STEM="${STEM%.py}"
  ENTRY_NAME="$STEM"
  adb_cmd shell "run-as $PACKAGE_ID sh -c 'rm -rf files/app/run; mkdir -p files/app/run'"
  stage_file "$RESOLVED" "run/${STEM}.py"
  echo "android.sh: staged $RESOLVED -> run/${STEM}.py"
  # Nested package examples only (e.g. examples/chango/chango.py) — never the
  # flat examples/*.py tree, which would push hundreds of unrelated siblings.
  # Stage sibling .py modules plus co-located assets (bmp/pbm/bin/…) and an
  # optional assets/ subdirectory (e.g. tower_climb/assets/*.bmp).
  ENTRY_DIR="$(dirname "$RESOLVED")"
  EXAMPLES_ROOT="$PYDEVICES_EXAMPLES_ROOT/src/examples"
  if [[ -d "$ENTRY_DIR" && "$ENTRY_DIR" != "$EXAMPLES_ROOT" && "$ENTRY_DIR" == "$EXAMPLES_ROOT"/* ]]; then
    for sibling in "$ENTRY_DIR"/*; do
      [[ -f "$sibling" ]] || continue
      sib_base="$(basename "$sibling")"
      [[ "$sib_base" == "${STEM}.py" ]] && continue
      case "$sib_base" in
        *.pyc|*.pyo|*~|.*|*.svg) continue ;;
      esac
      stage_file "$sibling" "run/${sib_base}"
      echo "android.sh: staged sibling ${sib_base}"
    done
    if [[ -d "$ENTRY_DIR/assets" ]]; then
      adb_cmd shell "run-as $PACKAGE_ID mkdir -p files/app/run/assets"
      for asset in "$ENTRY_DIR/assets"/*; do
        [[ -f "$asset" ]] || continue
        base="$(basename "$asset")"
        case "$base" in
          *.pyc|*.pyo|*~|.*|*.svg|gen_*.py) continue ;;
        esac
        stage_file "$asset" "run/assets/${base}"
        echo "android.sh: staged package asset assets/${base}"
      done
    fi
  fi
  # Flat examples that open ``examples/assets/...`` (cwd = files/app).
  SHARED_ASSETS="$EXAMPLES_ROOT/assets"
  if [[ -d "$SHARED_ASSETS" ]] && grep -qE 'examples/assets/|examples\\\\assets\\\\' "$RESOLVED" 2>/dev/null; then
    adb_cmd shell "run-as $PACKAGE_ID mkdir -p files/app/examples/assets"
    for asset in "$SHARED_ASSETS"/*; do
      [[ -f "$asset" ]] || continue
      base="$(basename "$asset")"
      case "$base" in
        *.pyc|*.pyo|*~|.*) continue ;;
      esac
      stage_file "$asset" "examples/assets/${base}"
      echo "android.sh: staged shared asset examples/assets/${base}"
    done
  fi
  stage_optional_csv deps "$DEPS_ARG"
  stage_optional_csv modules "$MODULES_ARG"
  stage_optional_csv manifests "$MANIFESTS_ARG"
elif [[ -n "$MODULE_ARG" ]]; then
  ENTRY_NAME="$MODULE_ARG"
  # Allow -m examples.foo -> foo if dotted
  if [[ "$ENTRY_NAME" == examples.* ]]; then
    ENTRY_NAME="${ENTRY_NAME#examples.}"
  fi
fi

if [[ -n "$HOLD_S" ]]; then
  # Oneshot examples draw once and return; Android splash / Activity teardown
  # then hide the frame. Hold with periodic show()+event pump so pixels stay up.
  hold_tmp="$(mktemp)"
  cat >"$hold_tmp" <<EOF
import importlib
import time

importlib.import_module(${ENTRY_NAME@Q})
try:
    from board_config import display_drv
except Exception:
    display_drv = None
_deadline = time.time() + float(${HOLD_S@Q})
while time.time() < _deadline:
    if display_drv is not None:
        try:
            display_drv.show()
        except Exception:
            pass
    try:
        import usdl2

        _e = usdl2.SDL_Event()
        while usdl2.SDL_PollEvent(_e):
            pass
    except Exception:
        pass
    time.sleep(0.05)
EOF
  stage_file "$hold_tmp" "run/_android_hold.py"
  rm -f "$hold_tmp"
  ENTRY_NAME="_android_hold"
  echo "android.sh: hold ${HOLD_S}s after entry via _android_hold"
fi

write_user_main "$ENTRY_NAME"
echo "android.sh: main.py -> import ${ENTRY_NAME}"
if [[ "$KIT" -eq 1 ]]; then
  write_app_file "run_argv" "kit"
  # lv_test_timer kit imports quit_inject from tools/; stage beside the entry.
  if [[ -f "$PYDEVICES_EXAMPLES_ROOT/tools/quit_inject.py" ]]; then
    stage_file "$PYDEVICES_EXAMPLES_ROOT/tools/quit_inject.py" "run/quit_inject.py"
    echo "android.sh: staged quit_inject.py for kit mode"
  fi
else
  adb_cmd shell "run-as $PACKAGE_ID sh -c 'rm -f files/app/run_argv'" || true
fi

adb_cmd logcat -c || true
relaunch

if [[ "$LOGCAT" -eq 1 && "$REPL" -eq 0 ]] && ! should_attach; then
  do_logcat
fi

if should_attach; then
  # Brief pause so force-stop/relaunch can bind the stdio sidecar before attach
  # retries (Ctrl-C during wait must not kill the host — attach.py holds SIGINT).
  sleep 0.4
  if [[ "$REPL" -eq 1 ]]; then
    attach_stdio repl
  else
    attach_stdio stdio
  fi
elif [[ "$LOGCAT" -eq 1 ]]; then
  do_logcat
fi
