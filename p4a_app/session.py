# SPDX-License-Identifier: MIT
"""Launcher sessions: run an example in a fresh process, then come home.

A launcher button does not run its example inside the launcher. It writes the
example's module name to ``launch_once`` and restarts the Runner; ``boot.py``
takes that name on the next start and runs it instead of ``main.py``. The
example gets its own process, so its own display and App, and nothing of the
launcher's screen is left under it.

When that example quits (Back), ``boot.py`` restarts the Runner once more.
``launch_once`` is gone by then, so the launcher comes back. A staged
``android.py`` entry never goes through here: Back still closes the Runner.

Android will not let a process that has gone away start an Activity, and a
running Runner can't start a second copy of itself (the Activity is
singleTask). So the restart goes through ``org.pydevices.runner.Relauncher``,
a translucent Activity in its own process: it is started while this one is
still on screen, ends this process, then starts the Runner.
"""

import os
import sys
import time
import traceback

ONCE = "launch_once"
_RELAUNCHER = "org.pydevices.runner.Relauncher"


def _path():
    return os.path.join(os.getcwd(), ONCE)


def take():
    """The module name a launcher button asked for, or ``""``. Consumes it."""
    path = _path()
    try:
        with open(path) as fh:
            entry = fh.read().strip()
    except OSError:
        return ""
    try:
        os.remove(path)
    except OSError:
        pass
    return entry


def restart():
    """End this process and start the Runner again. False if it can't.

    Returns only on failure; on success this process exits.
    """
    if sys.platform != "android":
        return False
    try:
        from jnius import autoclass

        act = autoclass("org.kivy.android.PythonActivity").mActivity
        intent = autoclass("android.content.Intent")()
        intent.setClassName(act.getPackageName(), _RELAUNCHER)
        intent.putExtra("pid", str(os.getpid()))
        act.startActivity(intent)
    except Exception:
        traceback.print_exc()
        return False
    sys.stdout.flush()
    # The Relauncher ends this process; wait for it rather than race it.
    time.sleep(3.0)
    os._exit(0)


def launch(entry):
    """Run module ``entry`` as a session of its own. False if it can't."""
    if sys.platform != "android":
        return False
    with open(_path(), "w") as fh:
        fh.write(entry)
    if restart():
        return True
    try:
        os.remove(_path())
    except OSError:
        pass
    return False
