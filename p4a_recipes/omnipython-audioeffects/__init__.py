# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""python-for-android recipe: omnipython-audioeffects (import audioeffects).

Pure Python on top of audiodsp, which the omnipython-audiodsp recipe carries.
"""

from pythonforandroid.recipe import PyProjectRecipe


class AudioeffectsRecipe(PyProjectRecipe):
    version = "0.5.1"
    name = "omnipython-audioeffects"
    depends = ["omnipython-audiodsp"]
    call_hostpython_via_targetpython = False


recipe = AudioeffectsRecipe()
