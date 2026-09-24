# SPDX-License-Identifier: MIT
"""python-for-android hooks for the runner (wired in via ``p4a.hook``).

``before_apk_build`` runs inside the dist directory that gradle is about to
compile, so the boot.py entry-point patch lands in the Java that ships. Patching
p4a's bootstrap source from build_android.sh missed on a first build, when
buildozer had not cloned p4a yet, and never reached an existing dist: the APK
then started ``main.pyc`` directly, skipping boot.py and its stdio sidecar
(android-runner#9).
"""

import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from patch_p4a_boot_entrypoint import patch_file  # noqa: E402

_ACTIVITY = "src/main/java/org/kivy/android/PythonActivity.java"


def before_apk_build(toolchain):
    path = pathlib.Path(os.getcwd()) / _ACTIVITY
    if not path.is_file():
        raise RuntimeError("p4a_hook: no %s in dist %s" % (_ACTIVITY, os.getcwd()))
    status = patch_file(path)
    print("p4a_hook: boot.py entry point %s: %s" % (status, path))
    if status == "no-match":
        raise RuntimeError("p4a_hook: getEntryPoint not found in %s" % path)
