# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Baked LVGL home screen for the PyDevices Android launcher APK.

Cold start never fetches. Buttons use omip (GitHub, the OmniPython index, then
micropython-lib) or pip
(TestPyPI primary, PyPI secondary) into ``user_pkgs/``, then import/run.

Default packaged ``main.py`` calls `start`. Do not auto-run on import so
mip can reload this module and refresh the UI via `build_ui`.

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

TESTPYPI = "https://test.pypi.org/simple/"
PYPI = "https://pypi.org/simple/"
OMIP_URL = "https://raw.githubusercontent.com/PyDevices/pydevices/main/lib/omip.py"

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
        "package": "github:PyDevices/gallery/lib/examples/piano.py",
        "entry": "piano",
    },
    {
        "label": "Drum machine",
        "kind": "mip",
        "package": (
            "github:PyDevices/gallery/packages/drum_machine.json",
            "github:PyDevices/gallery/packages/drum_seq.json",
        ),
        "entry": "drum_machine",
    },
    {
        "label": "lv_test_timer",
        "kind": "mip",
        "package": "github:PyDevices/gallery/lib/examples/lv_test_timer.py",
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


def _trust_android_certs():
    """Make HTTPS trust Android's own CA store, which the bundled Python can't find.

    Android keeps one PEM per hash-named file in a folder, not a bundle.
    """
    import ssl

    paths = ssl.get_default_verify_paths()
    if (paths.cafile and os.path.isfile(paths.cafile)) or (paths.capath and os.path.isdir(paths.capath)):
        return
    folder = "/system/etc/security/cacerts"
    if not os.path.isdir(folder):
        return

    def context(*args, **kwargs):
        ctx = ssl.create_default_context()
        for name in os.listdir(folder):
            try:
                ctx.load_verify_locations(cafile=os.path.join(folder, name))
            except (ssl.SSLError, OSError):
                pass
        return ctx

    ssl._create_default_https_context = context


def _omip():
    """Return omip: the copy baked into the APK, or one fetched into ``user_pkgs/``.

    An APK older than 0.2.9 has no ``utils/omip.py``, and its "Update launcher"
    button replaces only this file. So the first install after that update
    fetches omip itself. ``_trust_android_certs`` is only for that fetch: omip
    trusts Android's CA store on its own once it's here.
    """
    try:
        import utils.omip as omip

        return omip
    except ImportError:
        pass
    path = os.path.join(_user_pkgs_dir(), "omip.py")
    if not os.path.isfile(path):
        from urllib.request import Request, urlopen

        _set_status("fetching omip…")
        _trust_android_certs()
        with urlopen(Request(OMIP_URL, headers={"User-Agent": "launcher"}), timeout=30) as response:
            data = response.read()
        with open(path + ".part", "wb") as out:
            out.write(data)
        os.replace(path + ".part", path)
    import omip

    return omip


def _mip_install(packages):
    omip = _omip()

    target = _user_pkgs_dir()
    if isinstance(packages, str):
        packages = (packages,)
    for package in packages:
        _set_status("omip %s…" % package)
        omip.install(package, target=target, mpy=False, prompt=False)


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


def start():
    """Cold-start entry used by ``main.py``."""
    global _started
    import display_driver

    _user_pkgs_dir()
    if not _started:
        build_ui()
        _started = True
    display_driver.app.run()
