# SPDX-License-Identifier: MIT
"""Baked LVGL home screen for the PyDevices Android launcher APK.

Cold start never fetches. Buttons use mip (GitHub + PyDevices INDEX) or pip
(TestPyPI primary, PyPI secondary) into ``user_pkgs/``, then import/run.

Default packaged ``main.py`` calls :func:`start`. Do not auto-run on import so
mip can reload this module and refresh the UI via :func:`build_ui`.

On Android a button's example runs in a process of its own (``session.py``):
it gets a clean screen, and Back in it comes back here. Back here closes the
Runner.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
import traceback

INDEX = "https://PyDevices.github.io/mip"
TESTPYPI = "https://test.pypi.org/simple/"
PYPI = "https://pypi.org/simple/"

# Button registry: add entries here (or mip-update this file from GitHub).
BUTTONS = (
    {
        "label": "Update launcher",
        "kind": "mip",
        "package": "github:PyDevices/android-runner/p4a_app/launcher.py",
        "entry": "launcher",
        "reenter": True,
    },
    {
        "label": "Piano",
        "kind": "mip",
        "package": "github:PyDevices/pydevices-examples/lib/examples/piano.py",
        "entry": "piano",
    },
    {
        "label": "Drum machine",
        "kind": "mip",
        "package": (
            "github:PyDevices/pydevices-examples/packages/drum_machine.json",
            "github:PyDevices/pydevices-examples/packages/drum_seq.json",
        ),
        "entry": "drum_machine",
    },
    {
        "label": "lv_test_timer",
        "kind": "mip",
        "package": "github:PyDevices/pydevices-examples/lib/examples/lv_test_timer.py",
        "entry": "lv_test_timer",
    },
)

_status_lbl = None
_started = False


def _user_pkgs_dir():
    path = os.path.join(os.getcwd(), "user_pkgs")
    try:
        os.mkdir(path)
    except OSError:
        pass
    if path not in sys.path:
        sys.path.insert(0, path)
    return path


def _set_status(text):
    print("launcher:", text)
    if _status_lbl is not None:
        try:
            _status_lbl.set_text(text)
        except Exception:
            pass


def _pip_install(package):
    target = _user_pkgs_dir()
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        target,
        "-i",
        TESTPYPI,
        "--extra-index-url",
        PYPI,
        package,
    ]
    _set_status("pip install %s…" % package)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise RuntimeError(err[-1] if err else "pip failed (%s)" % proc.returncode)


def _mip_install(packages):
    import utils.mip as mip

    target = _user_pkgs_dir()
    if isinstance(packages, str):
        packages = (packages,)
    for package in packages:
        _set_status("mip %s…" % package)
        mip.install(package, index=INDEX, target=target, mpy=False)


def _reload_launcher_ui():
    """Load ``user_pkgs/launcher.py`` (or baked) and rebuild the home screen."""
    path = os.path.join(_user_pkgs_dir(), "launcher.py")
    if not os.path.isfile(path):
        # Fall back to reloading this module from wherever it was loaded.
        path = getattr(sys.modules.get("launcher"), "__file__", None)
    if not path or not os.path.isfile(path):
        build_ui()
        return
    spec = importlib.util.spec_from_file_location("launcher", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["launcher"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    mod.build_ui()


def _import_entry(entry, *, reenter=False):
    if reenter and entry == "launcher":
        _reload_launcher_ui()
        _set_status("Launcher updated.")
        return
    import session

    if session.launch(entry):
        return
    # No Android (a desktop smoke run): run it here, over the launcher.
    if entry in sys.modules:
        del sys.modules[entry]
    # Examples like lv_test_timer run UI + app.run() at import time.
    importlib.import_module(entry)


def _run_button(spec):
    try:
        kind = spec["kind"]
        if kind == "mip":
            _mip_install(spec["package"])
        elif kind == "pip":
            _pip_install(spec["package"])
        else:
            raise ValueError("unknown button kind: %r" % (kind,))
        entry = spec.get("entry")
        if entry:
            _set_status("Running %s…" % entry)
            _import_entry(entry, reenter=bool(spec.get("reenter")))
        else:
            _set_status("Done.")
    except Exception as exc:
        traceback.print_exc()
        _set_status("Error: %s" % exc)


def build_ui():
    """Build the home screen."""
    global _status_lbl
    import display_driver  # noqa: F401
    import lvgl as lv

    inst = None
    try:
        inst = display_driver.event_loop.current_instance()
    except Exception:
        pass
    if inst is not None:
        inst.disable()
    try:
        scr = lv.screen_active()
        scr.clean()

        title = lv.label(scr)
        title.set_text("PyDevices Launcher")
        title.align(lv.ALIGN.TOP_MID, 0, 16)

        hint = lv.label(scr)
        hint.set_text("Tap a button to fetch & run")
        hint.align(lv.ALIGN.TOP_MID, 0, 44)

        _status_lbl = lv.label(scr)
        _status_lbl.set_text("Ready.")
        try:
            _status_lbl.set_long_mode(lv.LABEL.LONG.WRAP)
        except Exception:
            pass
        _status_lbl.set_width(lv.pct(90))
        _status_lbl.align(lv.ALIGN.BOTTOM_MID, 0, -24)

        y = 80
        for spec in BUTTONS:
            btn = lv.button(scr)
            btn.set_size(lv.pct(86), 48)
            btn.align(lv.ALIGN.TOP_MID, 0, y)
            lbl = lv.label(btn)
            lbl.set_text(spec["label"])
            lbl.center()

            def _on_click(_e, s=spec):
                _run_button(s)

            btn.add_event_cb(_on_click, lv.EVENT.CLICKED, None)
            y += 60
    finally:
        if inst is not None:
            inst.enable()


def _settle_orientation(timeout_s=3.0):
    """Turn the Activity to the launcher's shape before its display exists.

    Back from a launcher session restarts the Runner (``session.py``). After a
    landscape example, the new process starts with the Activity still
    landscape, and the display turns it to portrait while SDL is creating its
    window and renderer. Some of those starts never show anything: the
    launcher draws its one frame, but the screen stays black until something
    redraws it, and a home screen waits for a tap (android-runner#28).
    Turning first, and waiting for the window and SDL's surface to take the
    new shape, gives the display a settled surface to start on.
    """
    if sys.platform != "android":
        return
    import time

    try:
        width = int(os.environ.get("PYDEVICES_WIDTH", "720"))
        height = int(os.environ.get("PYDEVICES_HEIGHT", "1280"))
        rotation = int(os.environ.get("PYDEVICES_ROTATION", "0")) % 360
    except ValueError:
        return
    if (rotation // 90) % 2:
        width, height = height, width
    landscape = width > height
    try:
        from jnius import autoclass

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        activity.setRequestedOrientation(0 if landscape else 1)  # ActivityInfo
        views = [activity.getWindow().getDecorView()]
        surface = autoclass("org.libsdl.app.SDLActivity").mSurface
        if surface is not None:
            views.append(surface)
    except Exception:
        traceback.print_exc()
        return

    def shapes():
        return tuple((view.getWidth(), view.getHeight()) for view in views)

    deadline = time.monotonic() + timeout_s
    last = None
    stable = 0
    while time.monotonic() < deadline:
        now = shapes()
        if now == last and all(w > 0 and h > 0 and (w > h) == landscape for w, h in now):
            stable += 1
            if stable >= 5:
                return
        else:
            stable = 0
        last = now
        time.sleep(0.02)


def start():
    """Cold-start entry used by ``main.py``."""
    global _started
    _settle_orientation()
    import display_driver

    _user_pkgs_dir()
    if not _started:
        build_ui()
        _started = True
    display_driver.app.run()
