# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices.

One recipe for the whole of the pydevices lib/ tree -- appdev, audiodev,
boarddev, displaydev, events, keys, multimer -- matching the single TestPyPI
distribution. There used to be one recipe per component, each restating the
dependency graph that is now internal to the distribution.

Pin the published floor so hostpython pip does not reuse a stale cached wheel
when ``version = None`` resolves against a warm cache.
"""

from pythonforandroid.recipe import PyProjectRecipe


class PydevicesRecipe(PyProjectRecipe):
    version = "0.0.17"
    name = "pydevices"
    depends = []
    call_hostpython_via_targetpython = False


recipe = PydevicesRecipe()
