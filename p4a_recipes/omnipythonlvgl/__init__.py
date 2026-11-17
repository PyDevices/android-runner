# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""python-for-android recipe: omnipython-lvgl (PyPI native Android wheel).

``version`` is an exact pin, like the omnipython recipe's: move the two
together. omnipython-lvgl 9.5.49 no longer ships ``display_driver`` (it moved
into omnipython 0.7), so an unpinned build that still carries omnipython 0.6.x
gets neither copy and the launcher can't start.
"""

from pythonforandroid.recipe import PyProjectRecipe


class OmnipythonLvglRecipe(PyProjectRecipe):
    version = "9.6.1"
    name = "omnipythonlvgl"
    depends = []
    call_hostpython_via_targetpython = False

    def get_pip_name(self):
        if self.version:
            return "omnipython-lvgl==%s" % self.version
        return "omnipython-lvgl"


recipe = OmnipythonLvglRecipe()
