# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""python-for-android recipe: omnipython-desktop (ships board_config/usdl2)."""

from pythonforandroid.recipe import PyProjectRecipe


class OmnipythonDesktopRecipe(PyProjectRecipe):
    version = "0.8.1"
    name = "omnipython-desktop"
    depends = ["sdl2", "omnipython"]
    call_hostpython_via_targetpython = False


recipe = OmnipythonDesktopRecipe()
