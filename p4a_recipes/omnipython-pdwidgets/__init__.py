# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""python-for-android recipe: omnipython-pdwidgets (import pdwidgets)."""

from pythonforandroid.recipe import PyProjectRecipe


class PdwidgetsRecipe(PyProjectRecipe):
    # Pin so hostpython pip does not reuse a stale wheel from cache.
    version = "0.0.26"
    name = "omnipython-pdwidgets"
    depends = [
        "omnipython",
        "omnipython-pygraphics",
        "omnipython-palettes",
    ]
    call_hostpython_via_targetpython = False


recipe = PdwidgetsRecipe()
