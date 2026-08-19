# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-pdwidgets (import pdwidgets)."""

from pythonforandroid.recipe import PyProjectRecipe


class PdwidgetsRecipe(PyProjectRecipe):
    # Pin so hostpython pip does not reuse a stale wheel from cache.
    version = "0.0.16"
    name = "pydevices-pdwidgets"
    depends = [
        "pydevices-appdev",
        "pydevices-pygraphics",
        "pydevices-multimer",
        "pydevices-palettes",
    ]
    call_hostpython_via_targetpython = False


recipe = PdwidgetsRecipe()
