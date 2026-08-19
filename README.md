# android-runner

Build engine for the **PyDevices Runner** APK (`org.pydevices.runner`) — the
generic, debuggable Android host that
[`pydevices/bin/android.py`](https://github.com/PyDevices/pydevices/blob/main/bin/android.py)
stages scripts onto.

**You almost certainly do not need this repository.** `android.py` downloads and
installs a prebuilt Runner from this repo's GitHub Releases:

```bash
android.py --install-apk
```

Using the Runner — staging scripts, the attach REPL, orientation, timers, audio,
Android TV — is documented in
[**pydevices/docs/android.md**](https://github.com/PyDevices/pydevices/blob/main/docs/android.md).
This repo is only how the APK gets built.

## What the APK contains

- **Runtime:** CPython under [python-for-android](https://python-for-android.readthedocs.io/) with the SDL2 bootstrap.
- **Payload:** native LVGL and pygraphics wheels plus the complete PyDevices runtime stack.
- **Stdio bridge:** `p4a_app/stdio_sidecar.py` listens on `127.0.0.1:18765` so `android.py` can attach bidirectional terminal stdio and a MicroPython-style REPL.
- **Startup:** `boot.py` sets up environment, path layout, and the sidecar, then runs whatever `android.py` staged into `run/`.

## Building it yourself

```bash
./build_android.sh -y
```

Output: `p4a_app/bin/runner-0.1.0-arm64-v8a_x86_64-debug.apk`

The build prerequisites, buildozer configuration, p4a recipes, and the
`getEntryPoint` patch are documented once, in
[android-template/docs/building.md](https://github.com/PyDevices/android-template/blob/main/docs/building.md) —
this repo used to carry a byte-identical copy.

## Releases

GitHub Actions builds the multi-ABI (`arm64-v8a`, `x86_64`) debug APK on release
tags and publishes `pydevices-runner-debug.apk` to GitHub Releases, which is what
`android.py --install-apk` fetches.
