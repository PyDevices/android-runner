# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-events (import events)."""

from pythonforandroid.recipe import PyProjectRecipe


class PydevicesEventsRecipe(PyProjectRecipe):
    version = "0.0.17"
    name = "pydevices-events"
    depends = []
    call_hostpython_via_targetpython = False


recipe = PydevicesEventsRecipe()
