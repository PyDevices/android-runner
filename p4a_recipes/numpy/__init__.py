# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""numpy for the Runner: python-for-android's recipe, plus one missing include.

numpy 2.3.0's unique.cpp uses std::unordered_map but includes only
<unordered_set>. The NDK 25 libc++ doesn't pull the map in through the set, so
the build stops there; the patch adds the include.
"""

from pythonforandroid.recipes.numpy import NumpyRecipe


class RunnerNumpyRecipe(NumpyRecipe):
    patches = ["unique-unordered-map.patch"]


recipe = RunnerNumpyRecipe()
