# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-audiodev (import audiodev)."""

from pythonforandroid.recipe import PyProjectRecipe


class PydevicesAudiodevRecipe(PyProjectRecipe):
    version = "0.0.17"
    name = "pydevices-audiodev"
    depends = ["sdl2"]
    call_hostpython_via_targetpython = False


recipe = PydevicesAudiodevRecipe()
