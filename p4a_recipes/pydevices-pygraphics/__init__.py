# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-pygraphics (import pygraphics)."""

from pythonforandroid.recipe import PyProjectRecipe


class PygraphicsRecipe(PyProjectRecipe):
    # Pin so hostpython pip does not reuse a stale wheel from cache.
    version = "0.0.32"
    name = "pydevices-pygraphics"
    depends = []
    call_hostpython_via_targetpython = False

    def get_pip_install_args(self, arch):
        # Upstream PyProjectRecipe only passes android_{ndk_api}_* tags. Our
        # cibuildwheel Android wheels are tagged android_21_* (PEP 738 baseline)
        # and remain valid for higher minSdk/ndk-api; include those tags so pip
        # can resolve pydevices-pygraphics==VERSION.
        opts = super().get_pip_install_args(arch)
        extra = []
        for opt in opts:
            if not opt.startswith("--platform=android_"):
                continue
            tag = opt.split("=", 1)[1]
            parts = tag.split("_", 2)  # android, API, arch...
            if len(parts) == 3 and parts[1] != "21":
                extra.append(f"--platform=android_21_{parts[2]}")
        insert_at = len(opts)
        for i, opt in enumerate(opts):
            if opt.startswith("--platform="):
                insert_at = i + 1
        for flag in extra:
            if flag not in opts:
                opts.insert(insert_at, flag)
                insert_at += 1
        return opts


recipe = PygraphicsRecipe()
