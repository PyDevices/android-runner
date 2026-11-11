# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-desktop (ships board_config/usdl2)."""

from pythonforandroid.recipe import PyProjectRecipe


class PydevicesDesktopRecipe(PyProjectRecipe):
    version = "0.7.9"
    name = "pydevices-desktop"
    depends = ["sdl2", "pydevices"]
    call_hostpython_via_targetpython = False


recipe = PydevicesDesktopRecipe()
