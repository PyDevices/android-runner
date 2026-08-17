# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-lvgl (TestPyPI native Android wheel)."""

from pythonforandroid.recipe import PyProjectRecipe


class PyDevicesLvglRecipe(PyProjectRecipe):
    # Optional — not in the paint milestone buildozer.spec requirements.
    version = None
    name = "pydeviceslvgl"
    depends = []
    call_hostpython_via_targetpython = False

    def get_pip_name(self):
        return "pydevices-lvgl"


recipe = PyDevicesLvglRecipe()
