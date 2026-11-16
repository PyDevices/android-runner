# Install the Runner

You don't build this repository to use the Runner. The `android.py` command
from [omnipython](https://github.com/PyDevices/omnipython) downloads the latest
Runner APK from this repository's GitHub Releases and installs it on a
connected phone or emulator:

```bash
android.py --install-apk
```

Staging a script, attaching a REPL, orientation, timers, audio and Android TV
are covered in [OmniPython's Android guide](https://github.com/PyDevices/omnipython/blob/main/docs/guides/run-on-android.md).
Building the APK yourself is in [CONTRIBUTING.md](../../CONTRIBUTING.md).
