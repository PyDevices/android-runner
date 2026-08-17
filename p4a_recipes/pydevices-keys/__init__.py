# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-keys (import keys)."""

from pythonforandroid.recipe import PyProjectRecipe


class PydevicesKeysRecipe(PyProjectRecipe):
    version = "0.0.17"
    name = "pydevices-keys"
    depends = []
    call_hostpython_via_targetpython = False


recipe = PydevicesKeysRecipe()
