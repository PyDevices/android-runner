# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-audioeffects (import audioeffects).

Pure Python on top of audiodsp, which the pydevices-audiodsp recipe carries.
"""

from pythonforandroid.recipe import PyProjectRecipe


class AudioeffectsRecipe(PyProjectRecipe):
    version = "0.3.1"
    name = "pydevices-audioeffects"
    depends = ["pydevices-audiodsp"]
    call_hostpython_via_targetpython = False


recipe = AudioeffectsRecipe()
