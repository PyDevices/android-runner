# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-multimer (import multimer)."""

from pythonforandroid.recipe import PyProjectRecipe


class MultimerRecipe(PyProjectRecipe):
    version = "0.0.17"
    name = "pydevices-multimer"
    depends = []
    call_hostpython_via_targetpython = False


recipe = MultimerRecipe()
