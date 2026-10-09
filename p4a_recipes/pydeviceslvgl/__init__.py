# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-lvgl (TestPyPI native Android wheel).

``version`` is an exact pin, like the pydevices recipe's: move the two
together. pydevices-lvgl 9.5.49 no longer ships ``display_driver`` (it moved
into pydevices 0.7), so an unpinned build that still carries pydevices 0.6.x
gets neither copy and the launcher can't start.
"""

from pythonforandroid.recipe import PyProjectRecipe


class PyDevicesLvglRecipe(PyProjectRecipe):
    version = "9.5.48"
    name = "pydeviceslvgl"
    depends = []
    call_hostpython_via_targetpython = False

    def get_pip_name(self):
        if self.version:
            return "pydevices-lvgl==%s" % self.version
        return "pydevices-lvgl"


recipe = PyDevicesLvglRecipe()
