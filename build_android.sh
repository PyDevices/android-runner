#!/usr/bin/env bash
# Build the p4a_app Android APK from this repo.
#
# Usage:
#   ./build_android.sh [options] [extra buildozer args after "android debug"...]
#
# Options:
#   -y, --yes, --no-prompt   Keep the current buildozer.spec title (no prompt)
#   --title NAME             Set the launcher title (no prompt)
#   --local-modules          Shadow TestPyPI with local displaydev/usdl2/audio
#                            (same as ANDROID_DEBUG_LOCAL_MODULES=1)
#   -h, --help               Show this help
#
# Interactive builds prompt for the launcher title (buildozer.spec `title`),
# defaulting to the current value. Non-TTY stdin also keeps the current title
# (same as -y) unless --title is given.
#
# Cache policy (important):
#   Never wipes p4a_app/.buildozer or ~/.buildozer between runs. Incremental
#   rebuilds reuse hostpython, python3, sdl2, and recipe builds. This script
#   refuses buildozer clean/distclean unless ALLOW_CLEAN=1.
#
# Environment:
#   VENV_DIR            Host build venv (default: $SCRIPT_DIR/.venv)
#   REQUIREMENTS        Host pip requirements (default: $SCRIPT_DIR/requirements-dev.txt)
#   ANDROID_HOME        Android SDK (default: ~/.buildozer/android/platform/android-sdk)
#   ANDROID_NDK_HOME    Android NDK (auto-detected under $ANDROID_HOME/ndk when unset)
#   JAVA_HOME           JDK for Android tooling (auto-detected from java on PATH when unset)
#   ALLOW_CLEAN         Set to 1 to permit clean/distclean args (default: refuse)
#   ANDROID_DEBUG_LOCAL_MODULES
#                       Set to 1 to sync local displaydev/, usdl2.py, and
#                       Android audio modules into p4a_app/ (debug only).
#                       Default (unset/0): remove those shadows so TestPyPI
#                       pydevices-displaydev + pydevices-desktop wheels win.
#
# Runtime deps are installed from TestPyPI via p4a PyProjectRecipe wrappers in p4a_recipes/.
# Before packaging, syncs sibling pydevices-examples/lib/utils → p4a_app/utils and overlays
# canonical pydevices/utils/mip.py (override with PYDEVICES_EXAMPLES_UTILS and
# PYDEVICES_PRODUCT_ROOT). Excludes spotapi symlink, __pycache__, *.md, *.sh.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
REQUIREMENTS="${REQUIREMENTS:-$SCRIPT_DIR/requirements-dev.txt}"
APP_DIR="$SCRIPT_DIR/p4a_app"
SPEC="$APP_DIR/buildozer.spec"
TESTPYPI_INDEX="${TESTPYPI_INDEX:-https://test.pypi.org/simple/}"

PYTHON="$VENV_DIR/bin/python3"
PIP="$VENV_DIR/bin/pip"
BUILDOZER="$VENV_DIR/bin/buildozer"

usage() {
    sed -n '2,38p' "$0" | sed 's/^# \?//'
    exit "${1:-0}"
}

NO_PROMPT=0
APP_TITLE=""
BUILDOZER_ARGS=()
# 1 = sync local displaydev/usdl2/audio into p4a_app (debug). Default: TestPyPI only.
ANDROID_DEBUG_LOCAL_MODULES="${ANDROID_DEBUG_LOCAL_MODULES:-0}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage 0
            ;;
        -y|--yes|--no-prompt)
            NO_PROMPT=1
            shift
            ;;
        --local-modules)
            ANDROID_DEBUG_LOCAL_MODULES=1
            shift
            ;;
        --title)
            if [[ $# -lt 2 || -z "${2:-}" ]]; then
                echo "--title requires a non-empty value" >&2
                exit 2
            fi
            APP_TITLE=$2
            NO_PROMPT=1
            shift 2
            ;;
        --title=*)
            APP_TITLE=${1#--title=}
            if [[ -z "$APP_TITLE" ]]; then
                echo "--title requires a non-empty value" >&2
                exit 2
            fi
            NO_PROMPT=1
            shift
            ;;
        *)
            BUILDOZER_ARGS+=("$1")
            shift
            ;;
    esac
done

refuse_cache_wipe_args() {
    # Do not forward buildozer targets that wipe p4a build trees.
    local a
    for a in "$@"; do
        case "$a" in
            clean|distclean|clean_builds|clean_dists|clean_download_cache|clean_all)
                if [[ "${ALLOW_CLEAN:-0}" != "1" ]]; then
                    echo "Refusing to run buildozer '$a' (would wipe Android build cache)." >&2
                    echo "Re-run with ALLOW_CLEAN=1 only if you intentionally want a cold rebuild." >&2
                    exit 2
                fi
                ;;
        esac
    done
}

refuse_cache_wipe_args "${BUILDOZER_ARGS[@]}"

read_spec_title() {
    local line
    line=$(grep -E '^title[[:space:]]*=' "$SPEC" | head -1) || true
    if [[ -z "$line" ]]; then
        echo "Missing title= in $SPEC" >&2
        exit 1
    fi
    echo "${line#*=}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

write_spec_title() {
    local title=$1
    local tmp
    tmp=$(mktemp)
    awk -v t="$title" '
        BEGIN { re = "^title[[:space:]]*=" }
        $0 ~ re { print "title = " t; next }
        { print }
    ' "$SPEC" >"$tmp"
    mv "$tmp" "$SPEC"
}

require_dir() {
    local path=$1
    local label=$2
    [[ -d "$path" ]] || {
        echo "Missing $label: $path" >&2
        exit 1
    }
}

require_file() {
    local path=$1
    local label=$2
    [[ -f "$path" ]] || {
        echo "Missing $label: $path" >&2
        exit 1
    }
}

ensure_build_venv() {
    require_file "$REQUIREMENTS" "requirements-dev.txt"
    if [[ ! -x "$PYTHON" ]]; then
        echo "==> Creating build venv at $VENV_DIR"
        python3 -m venv "$VENV_DIR"
    fi
    echo "==> Installing Android build Python deps in $VENV_DIR"
    "$PIP" install -q -U pip setuptools wheel
    "$PIP" install -q -r "$REQUIREMENTS"
    [[ -x "$BUILDOZER" ]] || {
        echo "buildozer not found in $VENV_DIR after pip install" >&2
        exit 1
    }
}

setup_android_env() {
    export BUILDOZER_ANDROID_HOME="${BUILDOZER_ANDROID_HOME:-$HOME/.buildozer/android}"
    export ANDROID_HOME="${ANDROID_HOME:-$BUILDOZER_ANDROID_HOME/platform/android-sdk}"
    export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"

    if [[ -z "${ANDROID_NDK_HOME:-}" && -d "$ANDROID_HOME/ndk" ]]; then
        local ndk
        ndk=$(find "$ANDROID_HOME/ndk" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort -V | tail -1)
        if [[ -n "$ndk" ]]; then
            export ANDROID_NDK_HOME="$ndk"
        fi
    fi
    # buildozer layout often keeps the NDK beside the SDK
    if [[ -z "${ANDROID_NDK_HOME:-}" ]]; then
        local ndk
        ndk=$(find "$BUILDOZER_ANDROID_HOME/platform" -maxdepth 1 -type d -name 'android-ndk-*' 2>/dev/null | sort -V | tail -1)
        if [[ -n "$ndk" ]]; then
            export ANDROID_NDK_HOME="$ndk"
        fi
    fi

    if [[ -z "${JAVA_HOME:-}" ]] && command -v java >/dev/null 2>&1; then
        JAVA_HOME=$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")
        export JAVA_HOME
    fi

    export VIRTUAL_ENV="$VENV_DIR"
    export PATH="$VENV_DIR/bin:$PATH"
}

sync_utils_from_examples() {
    # Bake pydevices-examples's app helpers, then overlay the portable product-owned mip.
    local src="${PYDEVICES_EXAMPLES_UTILS:-$SCRIPT_DIR/../pydevices-examples/lib/utils}"
    local hw="${PYDEVICES_PRODUCT_ROOT:-$SCRIPT_DIR/../pydevices}"
    local dst="$APP_DIR/utils"
    if [[ ! -d "$src" ]]; then
        echo "==> Skipping utils sync (missing $src); using existing $dst" >&2
        require_dir "$dst" "p4a_app/utils"
        require_file "$dst/path.py" "p4a_app/utils/path.py"
        return 0
    fi
    echo "==> Syncing utils from $src -> $dst"
    mkdir -p "$dst"
    rsync -a --delete \
        --exclude '__pycache__/' \
        --exclude 'spotapi' \
        --exclude '*.md' \
        --exclude '*.sh' \
        --delete-excluded \
        "$src/" "$dst/"
    require_file "$dst/path.py" "synced utils/path.py"
    require_file "$dst/tft_config.py" "synced utils/tft_config.py"
    require_dir "$dst/fonts" "synced utils/fonts"
    require_file "$hw/utils/mip.py" "pydevices utils/mip.py"
    rsync -a "$hw/utils/mip.py" "$dst/mip.py"
    require_file "$dst/mip.py" "synced utils/mip.py"
}

clear_android_local_module_shadows() {
    # Remove app-root shadows so site-packages (TestPyPI) win.
    local path
    for path in \
        "$APP_DIR/displaydev" \
        "$APP_DIR/usdl2.py" \
        "$APP_DIR/audiodev" \
        "$APP_DIR/androidaudio_session.py" \
        "$APP_DIR/sdl2audio.py" \
        "$APP_DIR/audiodev.py"
    do
        if [[ -e "$path" || -L "$path" ]]; then
            echo "==> Removing local module shadow: $path"
            rm -rf "$path"
        fi
    done
}

sync_android_audio_modules() {
    # Debug only: shadow TestPyPI pydevices-audiodev modules.
    local hw="${PYDEVICES_PRODUCT_ROOT:-$SCRIPT_DIR/../pydevices}"
    local audio_src="$hw/lib/audiodev"
    if [[ ! -f "$audio_src/__init__.py" || ! -f "$audio_src/sdl2_audio.py" ]]; then
        echo "==> Skipping Android audio sync (missing $audio_src)" >&2
        return 0
    fi
    echo "==> Syncing Android audiodev package from $audio_src -> $APP_DIR/audiodev"
    mkdir -p "$APP_DIR/audiodev"
    rsync -a --delete \
        --exclude '__pycache__/' \
        --exclude '*.md' \
        --delete-excluded \
        "$audio_src/" "$APP_DIR/audiodev/"
    require_file "$APP_DIR/audiodev/__init__.py" "synced audiodev/__init__.py"
    require_file "$APP_DIR/audiodev/sdl2_audio.py" "synced audiodev/sdl2_audio.py"
    require_file "$APP_DIR/audiodev/android_audio.py" "synced audiodev/android_audio.py"
}

sync_android_display_modules() {
    # Debug only: shadow TestPyPI displaydev / usdl2 (pydevices-desktop).
    local hw="${PYDEVICES_PRODUCT_ROOT:-$SCRIPT_DIR/../pydevices}"
    local disp_src="$hw/lib/displaydev"
    local usdl2_src="$hw/drivers/usdl2.py"
    if [[ -d "$disp_src" ]]; then
        echo "==> Syncing displaydev from $disp_src -> $APP_DIR/displaydev"
        mkdir -p "$APP_DIR/displaydev"
        rsync -a --delete \
            --exclude '__pycache__/' \
            --exclude '*.md' \
            --delete-excluded \
            "$disp_src/" "$APP_DIR/displaydev/"
        require_file "$APP_DIR/displaydev/androidsdl.py" "synced displaydev/androidsdl.py"
        require_file "$APP_DIR/displaydev/auto.py" "synced displaydev/auto.py"
    else
        echo "==> Skipping displaydev sync (missing $disp_src)" >&2
    fi
    if [[ -f "$usdl2_src" ]]; then
        echo "==> Syncing usdl2 from $usdl2_src -> $APP_DIR"
        cp -f "$usdl2_src" "$APP_DIR/usdl2.py"
        require_file "$APP_DIR/usdl2.py" "synced usdl2.py"
    else
        echo "==> Skipping usdl2 sync (missing $usdl2_src)" >&2
    fi
}

maybe_sync_android_local_modules() {
    case "${ANDROID_DEBUG_LOCAL_MODULES}" in
        1|true|TRUE|yes|YES)
            echo "==> ANDROID_DEBUG_LOCAL_MODULES=1: syncing local displaydev/usdl2/audio"
            sync_android_audio_modules
            sync_android_display_modules
            ;;
        *)
            echo "==> Using TestPyPI pydevices-displaydev + pydevices-desktop (no local module shadows)"
            clear_android_local_module_shadows
            ;;
    esac
}

ensure_build_venv
setup_android_env

require_dir "$APP_DIR" "p4a_app"
require_dir "$SCRIPT_DIR/p4a_recipes" "p4a_recipes"
require_file "$APP_DIR/boot.py" "p4a_app/boot.py"
require_file "$APP_DIR/main.py" "p4a_app/main.py"
require_file "$APP_DIR/paint.py" "p4a_app/paint.py"
require_file "$SPEC" "p4a_app/buildozer.spec"
sync_utils_from_examples
maybe_sync_android_local_modules

resolve_app_title() {
    local default title input
    default=$(read_spec_title)
    if [[ -n "$APP_TITLE" ]]; then
        title=$APP_TITLE
    elif [[ "$NO_PROMPT" -eq 1 ]] || [[ ! -t 0 ]]; then
        title=$default
        if [[ ! -t 0 && "$NO_PROMPT" -eq 0 && -z "$APP_TITLE" ]]; then
            echo "==> Non-interactive stdin: keeping app title: $title"
        fi
    else
        read -r -p "App launcher title [$default]: " input || true
        title=${input:-$default}
    fi
    if [[ -z "$title" ]]; then
        echo "App title must not be empty" >&2
        exit 1
    fi
    if [[ "$title" != "$default" ]]; then
        write_spec_title "$title"
        echo "==> Updated $SPEC title -> $title"
    else
        echo "==> App title: $title"
    fi
}

resolve_app_title

echo "==> Building Android APK in $APP_DIR"
echo "    venv=$VENV_DIR"
echo "    TestPyPI=$TESTPYPI_INDEX"
echo "    ANDROID_DEBUG_LOCAL_MODULES=$ANDROID_DEBUG_LOCAL_MODULES"
echo "    ANDROID_HOME=$ANDROID_HOME"
if [[ -n "${ANDROID_NDK_HOME:-}" ]]; then
    echo "    ANDROID_NDK_HOME=$ANDROID_NDK_HOME"
else
    echo "    ANDROID_NDK_HOME=(unset — buildozer may download NDK on first run)"
fi
if [[ -n "${JAVA_HOME:-}" ]]; then
    echo "    JAVA_HOME=$JAVA_HOME"
fi
if [[ -d "$APP_DIR/.buildozer" ]]; then
    echo "    cache=$APP_DIR/.buildozer (reusing; not cleared)"
else
    echo "    cache=$APP_DIR/.buildozer (first build — will be created)"
fi

# p4a sdl2 hardcodes main.py; prefer boot.py (setup) so main.py is user code.
patch_p4a_boot_entrypoint() {
    local py="$SCRIPT_DIR/scripts/patch_p4a_boot_entrypoint.py"
    local roots=(
        "$APP_DIR/.buildozer/android/platform/python-for-android/pythonforandroid/bootstraps/sdl2/build/src/main/java/org/kivy/android/PythonActivity.java"
        "$APP_DIR/.buildozer/android/platform/build-arm64-v8a_x86_64/dists/launcher/src/main/java/org/kivy/android/PythonActivity.java"
        "$APP_DIR/.buildozer/android/platform/build-arm64-v8a/dists/launcher/src/main/java/org/kivy/android/PythonActivity.java"
    )
    local f
    if [[ ! -f "$py" ]]; then
        echo "Missing $py" >&2
        exit 1
    fi
    echo "==> Patching p4a getEntryPoint to prefer boot.py"
    "$VENV_DIR/bin/python3" "$py" "${roots[@]}" || true
    for f in "${roots[@]}"; do
        if [[ -f "$f" ]] && grep -q 'entryPoints.add("boot.pyc")' "$f"; then
            touch "$f"
        fi
    done
}

cd "$APP_DIR"
patch_p4a_boot_entrypoint
# Always "android debug" — never "android clean". Extra args are flags only.
"$BUILDOZER" android debug "${BUILDOZER_ARGS[@]}"

echo "==> APK output:"
ls -1 "$APP_DIR"/bin/*.apk
