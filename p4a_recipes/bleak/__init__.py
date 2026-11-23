# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""python-for-android recipe: bleak, for Bluetooth LE as a central.

bleak's wheel is pure Python, so pip installs it as it does the OmniPython
packages. Its python-for-android backend (``bleak.backends.p4android``) also
needs two Java classes, the scan and GATT callbacks it ships as source beside
that backend; they're copied in for the APK's build to compile. bleak's own
recipe does the same from a git checkout of its development branch, so this
one exists to pin a release from PyPI.
"""

import os
from os.path import join

import sh
from pythonforandroid.recipe import PyProjectRecipe
from pythonforandroid.toolchain import info, shprint


class BleakRecipe(PyProjectRecipe):
    version = "3.1.0"
    name = "bleak"
    depends = ["pyjnius", "android"]
    call_hostpython_via_targetpython = False

    def postbuild_arch(self, arch):
        super().postbuild_arch(arch)
        java = join(self.ctx.get_python_install_dir(arch.arch), "bleak", "backends", "p4android", "java")
        if not os.path.isdir(java):
            raise RuntimeError("bleak %s has no Java sources at %s: its p4android backend can't run" % (self.version, java))
        info("Copying bleak's Java callbacks")
        shprint(sh.cp, "-a", join(java, "."), self.ctx.javaclass_dir)


recipe = BleakRecipe()
