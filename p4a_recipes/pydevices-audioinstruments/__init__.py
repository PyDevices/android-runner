# SPDX-License-Identifier: MIT
"""python-for-android recipe: pydevices-audioinstruments (import audioinstruments).

Pure Python on top of audiodsp, which the pydevices-audiodsp recipe carries.
"""

from pythonforandroid.recipe import PyProjectRecipe


class AudioinstrumentsRecipe(PyProjectRecipe):
    version = "0.3.1"
    name = "pydevices-audioinstruments"
    depends = ["pydevices-audiodsp"]
    call_hostpython_via_targetpython = False


recipe = AudioinstrumentsRecipe()
