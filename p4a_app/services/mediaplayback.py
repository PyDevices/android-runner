# SPDX-License-Identifier: MIT
"""Keep-alive entry for the mediaPlayback foreground service.

PCM playback stays in the main PythonActivity process (audiodev.sdl2_audio / OpenSL).
This service process exists so Android 14+ grants while-in-use mediaPlayback
capability and AudioHardening does not silence USAGE_MEDIA streams.
"""

from os import environ
from time import sleep

# Optional argument from Service.start(..., argument)
_ = environ.get("PYTHON_SERVICE_ARGUMENT", "")

while True:
    sleep(3600)
