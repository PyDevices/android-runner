# android-runner

android-runner builds the PyDevices Runner, an Android app that runs PyDevices
Python scripts on a phone, tablet or Android TV, with an attached REPL, so
`android.py` can stage a script and run it without building an APK of your own.

You almost certainly don't need to build this repository. `android.py`, the
single-file command from [pydevices](https://github.com/PyDevices/pydevices),
downloads the latest Runner from this repository's GitHub Releases and installs
it on a connected device or emulator:

```bash
android.py --install-apk
```

Staging scripts, the REPL, orientation, timers, audio and Android TV are in
[PyDevices' Android guide](https://github.com/PyDevices/pydevices/blob/main/docs/guides/run-on-android.md).

To work on the Runner itself, try its startup path on your desktop first. This
installs the PyDevices desktop packages into a virtual environment, runs the
Runner's `boot.py` and launcher under Xvfb for a few seconds, and checks that a
timer fires:

```bash
./scripts/test_desktop.sh
```

```text
== boot.py → main.py (the launcher, for a few seconds) ==
SDLDisplay: initialized.
SMOKE_TIMER signal
multimer on cpython/linux: source=signal delivery=bytecode wakes_blocking=True strategy=exit_hook
Desktop smoke passed: the launcher ran for the whole window and a timer fired
```

That output is trimmed to its key lines. Building the APK is in
[CONTRIBUTING.md](CONTRIBUTING.md).

[Docs](https://github.com/PyDevices/android-runner/blob/main/docs/index.md) · [Examples](https://pydevices.github.io/pydevices-examples/gallery/) · [Roadmap](ROADMAP.md)

OmniPython is made by [PyDevices](https://pydevices.com).
