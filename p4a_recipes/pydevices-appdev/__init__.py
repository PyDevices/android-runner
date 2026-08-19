# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-appdev (import appdev)."""

from pythonforandroid.recipe import PyProjectRecipe


class AppdevRecipe(PyProjectRecipe):
    version = "0.0.17"
    name = "pydevices-appdev"
    depends = ["pydevices-events", "pydevices-keys", "pydevices-multimer"]
    call_hostpython_via_targetpython = False


recipe = AppdevRecipe()
