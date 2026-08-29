# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices.

One recipe for the whole of the pydevices lib/ tree -- appdev, audiodev,
boarddev, displaydev, events, keys, multimer -- matching the single TestPyPI
distribution. There used to be one recipe per component, each restating the
dependency graph that is now internal to the distribution.

p4a's ``version`` attribute is an exact pin, not a floor: pip installs this
version and no other. Pin it explicitly (rather than ``version = None``) so
hostpython pip does not resolve against whatever happens to be cached.
"""

from pythonforandroid.recipe import PyProjectRecipe


class PydevicesRecipe(PyProjectRecipe):
    version = "0.3.7"
    name = "pydevices"
    depends = []
    call_hostpython_via_targetpython = False


recipe = PydevicesRecipe()
