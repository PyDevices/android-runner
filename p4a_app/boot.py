# SPDX-License-Identifier: MIT
# Activity entry via build_android.sh getEntryPoint patch (prefer boot over main).
"""MicroPython-shaped startup: setup, then ``main.py`` if present, else REPL.

Mirrors firmware ``boot.py`` → optional ``main.py`` → REPL. Setup (env, path
layout, stdio sidecar) lives here so ``main.py`` is free for user code or may
be omitted for a clean attach REPL. Upstream p4a/sdl2 hardcodes ``main.py``;
``scripts/patch_p4a_boot_entrypoint.py`` makes the Activity prefer this file.
"""

from __future__ import annotations

import importlib
import os
import runpy
import sys
import time
import traceback

try:
    import utils.path  # noqa: F401
except ImportError:
    pass

# Phone defaults for packaged desktop board_config (env-driven sizes).
# For TV / 10-foot UI, import board_config_tv from main.py before board_config.
if sys.platform == "android":
    os.environ.setdefault("PYDEVICES_WIDTH", "720")
    os.environ.setdefault("PYDEVICES_HEIGHT", "1280")
    os.environ.setdefault("PYDEVICES_SCALE", "1.0")
    os.environ.setdefault("PYDEVICES_ROTATION", "0")
    # Must be set before ``import multimer`` (via board_config). CPython
    # SDL_AddTimer callbacks are not on the GLES thread — sdl2 timers cause
    # EGL_BAD_ACCESS and a blank/frozen display after the first presents.
    os.environ.setdefault("MULTIMER_BACKEND", "threading")


def _ensure_dir(name):
    path = os.path.join(os.getcwd(), name)
    try:
        os.mkdir(path)
    except OSError:
        pass
    if path not in sys.path:
        sys.path.insert(0, path)
    return path


def _read_text(name):
    try:
        with open(name, "r") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _apply_run_argv():
    """Optional ``run_argv``: whitespace-separated tokens appended to sys.argv."""
    raw = _read_text("run_argv")
    if not raw:
        return
    for tok in raw.split():
        if tok and tok not in sys.argv:
            sys.argv.append(tok)


def _mark_entry_done():
    try:
        import stdio_sidecar

        stdio_sidecar.mark_entry_done()
    except Exception as exc:
        try:
            import stdio_sidecar

            stdio_sidecar.log_exc("mark_entry_done", exc)
        except Exception:
            print("stdio_sidecar: mark_entry_done:", exc, flush=True)


def _park():
    """Keep the Activity alive so ``android.sh -i`` can own the REPL."""
    if sys.platform != "android":
        return
    while True:
        try:
            time.sleep(3600)
        except KeyboardInterrupt:
            print("KeyboardInterrupt", flush=True)


def _run_main_py():
    """Execute ``./main.py`` as ``__main__`` (MicroPython-style)."""
    path = os.path.join(os.getcwd(), "main.py")
    if not os.path.isfile(path):
        return False
    try:
        runpy.run_path(path, run_name="__main__")
    except KeyboardInterrupt:
        print("KeyboardInterrupt", flush=True)
    except Exception:
        traceback.print_exc()
    return True


def _run_legacy_run_entry():
    """Backward compat: ``run_entry`` module name (pre-boot.py android.sh)."""
    entry = _read_text("run_entry")
    if not entry:
        return False
    try:
        importlib.import_module(entry)
    except KeyboardInterrupt:
        print("KeyboardInterrupt", flush=True)
    except Exception:
        traceback.print_exc()
    return True


# user_pkgs first so a mip-updated launcher.py wins over the baked copy.
_ensure_dir("user_pkgs")
_ensure_dir("run")
_apply_run_argv()

# Localhost stdio bridge for ``android.sh`` attach / ``-i`` (before user main).
if sys.platform == "android":
    try:
        import stdio_sidecar

        stdio_sidecar.start()
    except Exception as _stdio_exc:
        try:
            import stdio_sidecar as _ss

            _ss.log_exc("start", _stdio_exc)
        except Exception:
            print("stdio_sidecar: start:", _stdio_exc, flush=True)

try:
    if not _run_main_py():
        # Legacy: older android.sh wrote run_entry instead of main.py.
        _run_legacy_run_entry()
finally:
    _mark_entry_done()

# After main returns, or when main.py is omitted — keep Activity up for attach.
_park()
