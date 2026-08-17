# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-palettes (import palettes)."""

from pythonforandroid.recipe import PyProjectRecipe


class PalettesRecipe(PyProjectRecipe):
    version = "0.0.8"
    name = "pydevices-palettes"
    depends = []
    call_hostpython_via_targetpython = False


recipe = PalettesRecipe()
