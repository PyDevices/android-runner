# pydevices-android-runner

Pre-built Android Runner APK build engine for the [PyDevices](https://github.com/PyDevices/pydevices) product stack.

This repository compiles the generic, debuggable **PyDevices Runner** APK (`org.pydevices.runner`) distributed via GitHub Releases. The Runner APK contains CPython, SDL2, native LVGL/pygraphics wheels, the complete PyDevices runtime stack, and the stdio socket bridge.

Host scripts are executed directly on the device using **`pydevices/bin/android.py`** without requiring end users to compile their own APK.

## Runner Architecture

* **Runtime:** CPython under **python-for-android** with the **SDL2 bootstrap**.
* **Stdio Bridge:** `p4a_app/stdio_sidecar.py` listens on `127.0.0.1:18765`, enabling `android.py` to attach bidirectional terminal stdio and a MicroPython-style REPL (`>>>`).
* **MicroPython Startup:** `boot.py` initializes environment variables, path layout, and stdio sidecar, then loads the user entry staged in `run/` by `android.py`.

## Building the Debug APK

```bash
./build_android.sh -y
```

Output: `p4a_app/bin/runner-0.1.0-arm64-v8a_x86_64-debug.apk`

## Releases & CI

GitHub Actions automatically builds the multi-ABI (`arm64-v8a`, `x86_64`) debug APK on new release tags and publishes `pydevices-runner-debug.apk` to GitHub Releases for `pydevices/bin/android.py` to download on demand.
