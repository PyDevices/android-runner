# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-displaydev (import displaydev).

Pin the published floor so hostpython pip does not reuse a stale cached wheel
when ``version = None`` resolves against a warm cache.
"""

from pythonforandroid.recipe import PyProjectRecipe


class DisplaydevRecipe(PyProjectRecipe):
    version = "0.0.17"
    name = "pydevices-displaydev"
    depends = ["pydevices-events", "pydevices-keys"]
    call_hostpython_via_targetpython = False


recipe = DisplaydevRecipe()
