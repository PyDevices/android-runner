# SPDX-License-Identifier: MIT
"""python-for-android recipe for the pydevices-audioif native wheel."""

from pythonforandroid.recipe import PyProjectRecipe


class AudioifRecipe(PyProjectRecipe):
    version = "0.0.4"
    name = "pydevices-audioif"
    depends = []
    call_hostpython_via_targetpython = False

    def get_pip_name(self):
        return "pydevices-audioif"

    def get_pip_install_args(self, arch):
        opts = super().get_pip_install_args(arch)
        extra = []
        for opt in opts:
            if opt.startswith("--platform=android_"):
                parts = opt.split("=", 1)[1].split("_", 2)
                if len(parts) == 3 and parts[1] != "21":
                    extra.append("--platform=android_21_" + parts[2])
        insert_at = next((i + 1 for i, opt in reversed(list(enumerate(opts))) if opt.startswith("--platform=")), len(opts))
        for flag in extra:
            if flag not in opts:
                opts.insert(insert_at, flag)
                insert_at += 1
        return opts


recipe = AudioifRecipe()
