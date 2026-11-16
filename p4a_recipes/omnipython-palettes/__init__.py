# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""python-for-android recipe: omnipython-palettes (import palettes)."""

from pythonforandroid.recipe import PyProjectRecipe


class PalettesRecipe(PyProjectRecipe):
    version = "0.0.15"
    name = "omnipython-palettes"
    depends = []
    call_hostpython_via_targetpython = False


recipe = PalettesRecipe()
