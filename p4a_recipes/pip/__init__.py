# SPDX-License-Identifier: MIT
"""python-for-android recipe: pip (PyPI wheel for on-device installs)."""

from pythonforandroid.recipe import PyProjectRecipe


class PipRecipe(PyProjectRecipe):
    version = None
    name = "pip"
    depends = ["setuptools"]
    call_hostpython_via_targetpython = False


recipe = PipRecipe()
