# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Android TV / Fire OS framebuffer env for packaged ``board_config``.

Import this from ``main.py`` *before* ``paint`` (which imports ``board_config``
from omnipython-desktop) so width/height match a landscape 10-foot UI:

    import board_config_tv  # noqa: F401
    import paint

Or set the same ``OMNIPYTHON_*`` variables in the environment before launch.
"""

import os

os.environ.setdefault("OMNIPYTHON_WIDTH", "1280")
os.environ.setdefault("OMNIPYTHON_HEIGHT", "720")
os.environ.setdefault("OMNIPYTHON_SCALE", "1.0")
os.environ.setdefault("OMNIPYTHON_ROTATION", "0")
