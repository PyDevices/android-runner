# SPDX-License-Identifier: MIT
"""Android TV / Fire OS framebuffer env for packaged ``board_config``.

Import this from ``main.py`` *before* ``paint`` (which imports ``board_config``
from pydevices-desktop) so width/height match a landscape 10-foot UI:

    import board_config_tv  # noqa: F401
    import paint

Or set the same ``PYDEVICES_*`` variables in the environment before launch.
"""

import os

os.environ.setdefault("PYDEVICES_WIDTH", "1280")
os.environ.setdefault("PYDEVICES_HEIGHT", "720")
os.environ.setdefault("PYDEVICES_SCALE", "1.0")
os.environ.setdefault("PYDEVICES_ROTATION", "0")
