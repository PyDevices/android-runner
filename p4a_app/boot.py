# SPDX-License-Identifier: MIT
# Activity entry via build_android.sh getEntryPoint patch (prefer boot over main).
"""MicroPython-shaped startup: setup, then ``main.py`` if present, else REPL.

Mirrors firmware ``boot.py`` → optional ``main.py`` → REPL. Setup (env, path
layout, stdio sidecar) lives here so ``main.py`` is free for user code or may
be omitted for a clean attach REPL. Upstream p4a/sdl2 hardcodes ``main.py``;
``scripts/p4a_hook.py`` patches the Activity to prefer this file.
"""

from __future__ import annotations

import importlib
import os
import runpy
import sys
import time
import traceback

# Phone defaults for packaged desktop board_config (env-driven sizes).
# For TV / 10-foot UI, import board_config_tv from main.py before board_config.
if sys.platform == "android":
    os.environ.setdefault("PYDEVICES_WIDTH", "720")
    os.environ.setdefault("PYDEVICES_HEIGHT", "1280")
    os.environ.setdefault("PYDEVICES_SCALE", "1.0")
    os.environ.setdefault("PYDEVICES_ROTATION", "0")


def _ensure_dir(name):
    path = os.path.join(os.getcwd(), name)
    try:
        os.mkdir(path)
    except OSError:
        pass
    if path not in sys.path:
        sys.path.insert(0, path)
    return path


def _add_utils():
    """Put the baked helpers in ``utils/`` (tft_config, tft_text, fonts) on ``sys.path``.

    Staged examples import them by bare name. They go just after the app
    directory, where pydevices-examples' ``utils/path.py`` used to put them.
    """
    cwd = os.getcwd()
    path = os.path.join(cwd, "utils")
    if path in sys.path:
        return
    at = 0
    for index, entry in enumerate(sys.path):
        if entry in ("", ".", cwd):
            at = index + 1
            break
    sys.path.insert(at, path)


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


def _sidecar(name):
    """Ask ``stdio_sidecar`` a yes/no question; False when it isn't running."""
    try:
        import stdio_sidecar

        return bool(getattr(stdio_sidecar, name)())
    except Exception:
        return False


def _app_quit():
    """True when the app the entry ran has quit (Back, or its own ``quit()``)."""
    mod = sys.modules.get("appdev.app")
    app = getattr(getattr(mod, "App", None), "_current_app", None)
    return app is not None and bool(getattr(app, "_quit_requested", False))


def _finish_activity():
    """Close the Activity so Back lands on the home screen. True if asked.

    Returning from this file then ends the process: p4a finalizes Python and
    exits, and ``SDLActivity.onDestroy`` is waiting on exactly that. A daemon
    watchdog exits anyway if a stray non-daemon thread holds finalization.
    """
    if sys.platform != "android":
        return False
    # Let an attached ``android.py`` stdio session drain the last output.
    deadline = time.monotonic() + 2.0
    while _sidecar("client_attached") and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        from jnius import autoclass

        autoclass("org.kivy.android.PythonActivity").mActivity.finish()
    except Exception:
        traceback.print_exc()
        return False

    def _watchdog():
        time.sleep(3.0)
        os._exit(0)

    import threading

    threading.Thread(target=_watchdog, name="finish_watchdog", daemon=True).start()
    return True


_K_AC_BACK = 1073742094  # SDLK_AC_BACK
_sdl_events = None


def _back_pressed():
    """Drain SDL's queue; True on Back or a system quit.

    SDL takes every key, Back included, so once nothing polls it Back does
    nothing at all. While parked without a REPL, poll it here. An app's
    teardown has usually shut SDL down, and a script with no display never
    started it; SDL's keyboard lives in its video subsystem, so bring that
    up. It opens no window.
    """
    global _sdl_events
    if _sdl_events is None:
        try:
            import usdl2

            usdl2.SDL_InitSubSystem(usdl2.SDL_INIT_VIDEO)
            _sdl_events = (usdl2, usdl2.SDL_Event())
        except Exception:
            traceback.print_exc()
            _sdl_events = False
    if not _sdl_events:
        return False
    usdl2, event = _sdl_events
    hit = False
    try:
        while usdl2.SDL_PollEvent(event):
            if event.type == usdl2.SDL_QUIT:
                hit = True
            elif event.type == usdl2.SDL_KEYDOWN and event.key.keysym.sym == _K_AC_BACK:
                hit = True
    except Exception:
        return False
    return hit


def _leave():
    """Back out of this start: to the launcher from a launcher session, else close.

    True if it's on its way; a launcher session's restart never returns.
    """
    if _launched:
        import session

        if session.restart():
            return True
    return _finish_activity()


def _park():
    """Keep the Activity alive so ``android.py -i`` can own the REPL.

    Back still leaves while no REPL is attached. Returns when it does.
    """
    if sys.platform != "android":
        return
    while True:
        try:
            if not _sidecar("repl_attached") and _back_pressed():
                if _leave():
                    return
            time.sleep(0.1)
        except KeyboardInterrupt:
            print("KeyboardInterrupt", flush=True)


def _run_main_py():
    """Execute ``./main.py`` as ``__main__`` (MicroPython-style).

    A staged ``main.py`` wins; otherwise the APK's baked ``main.pyc`` (p4a ships
    app sources compiled) runs the launcher.
    """
    for name in ("main.py", "main.pyc"):
        path = os.path.join(os.getcwd(), name)
        if os.path.isfile(path):
            break
    else:
        return False
    try:
        runpy.run_path(path, run_name="__main__")
    except KeyboardInterrupt:
        print("KeyboardInterrupt", flush=True)
        return True
    except Exception:
        traceback.print_exc()
        return True
    _drive_live_app()
    return True


def _drive_live_app():
    """Run an ``appdev.App`` that outlived ``main.py``, as its exit hook would.

    Non-LVGL examples create an App and let the script end; on desktop an
    interpreter exit hook then takes the main thread and pumps the app. The
    Activity never exits, so that hook never fires and the app's timers never
    run: a black screen and no touch. Pump it here instead.
    """
    mod = sys.modules.get("appdev.app")
    app = getattr(getattr(mod, "App", None), "_current_app", None)
    if app is None or getattr(app, "_quit_requested", False):
        return
    try:
        app.run()
    except KeyboardInterrupt:
        print("KeyboardInterrupt", flush=True)
    except SystemExit:
        pass
    except Exception:
        traceback.print_exc()


def _run_launched(entry):
    """Run the module a launcher button asked for (``session.py``) as the entry."""
    try:
        if entry in sys.modules:
            del sys.modules[entry]
        importlib.import_module(entry)
    except KeyboardInterrupt:
        print("KeyboardInterrupt", flush=True)
        return True
    except Exception:
        traceback.print_exc()
        return True
    _drive_live_app()
    return True


def _run_legacy_run_entry():
    """Backward compat: ``run_entry`` module name (pre-boot.py host runner)."""
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


_add_utils()
# user_pkgs first so a mip-updated launcher.py wins over the baked copy.
_ensure_dir("user_pkgs")
_ensure_dir("run")
_apply_run_argv()

# Localhost stdio bridge for ``android.py`` attach / ``-i`` (before user main).
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

# A launcher button's example, started in this fresh process (session.py).
try:
    import session

    _launched = session.take()
except Exception:
    traceback.print_exc()
    _launched = ""

_ran = False
try:
    if _launched:
        _ran = _run_launched(_launched)
    else:
        _ran = _run_main_py() or _run_legacy_run_entry()
finally:
    _mark_entry_done()

# Back quit the app: close the Activity, back to the home screen, or from a
# launcher session back to the launcher. Otherwise (the entry returned, failed,
# or ``android.py -i`` is attached) keep the Activity up for attach, as a board
# keeps running after main.py.
if not (_ran and _app_quit() and not _sidecar("repl_attached") and _leave()):
    _park()
