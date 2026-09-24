# Newcomer's guide to android-runner

android-runner builds the PyDevices Runner APK, the generic Android host used by the `android.py` command from [pydevices](https://github.com/PyDevices/pydevices).

Most users should not build this repository. Install the published Runner through the product command:

```bash
android.py --install-apk
```

Then follow [PyDevices' Android guide](https://github.com/PyDevices/pydevices/blob/main/docs/android.md) to stage applications, attach a REPL, and configure device behavior.

## Runtime path

```text
android.py installs the Runner and stages a program
                 |
                 v
Runner Activity (CPython with SDL2)
                 |
                 v
boot.py prepares user_pkgs and run, then starts the stdio sidecar
                 |
                 v
main.py (android.py's "import <script>" from run/), or the bundled launcher
                 |
                 v
Activity remains available for an attached REPL
```

`boot.py` creates the staged-program import paths, starts `stdio_sidecar.py` on loopback port 18765 on Android, runs `./main.py` when present, and keeps the Activity available for attach. When you stage a script, `android.py` copies it to `run/<script>.py` and writes a top-level `main.py` that imports it. The bundled `main.py` only starts the default launcher; staging a program replaces that entry.

## Repository map

| Path | Purpose |
|---|---|
| `build_android.sh` | Creates the build environment, synchronizes helpers, and invokes Buildozer. |
| `p4a_app/boot.py` | Runtime setup and staged-program entrypoint. |
| `p4a_app/stdio_sidecar.py` | Loopback stdio and REPL bridge. |
| `p4a_app/main.py` and `launcher.py` | Bundled default home application. |
| `p4a_recipes/` | python-for-android recipes for PyDevices packages. |
| `scripts/p4a_hook.py` + `scripts/patch_p4a_boot_entrypoint.py` | Patch the built dist so the Activity starts `boot.py`. |
| `scripts/test_desktop.sh` | Short desktop smoke of `boot.py` to `main.py`. |

## Build boundary

Build only when changing the APK host, recipes, or packaged payload. Run `./build_android.sh -y`; it preserves build caches unless an explicit clean is authorized. The build normally installs runtime dependencies from TestPyPI. In a multi-repository checkout it refreshes helpers from sibling `pydevices-examples` and `pydevices`; a standalone checkout keeps checked-in helpers.

This repository owns the shared build machinery that android-template synchronizes. Make shared build changes here first. Detailed Buildozer and python-for-android prerequisites live in [android-template's build guide](https://github.com/PyDevices/android-template/blob/main/docs/building.md).

## A safe first contribution

Trace a staged script from `boot.py` through the sidecar before changing runtime behavior. For build work, start with `./build_android.sh --help` and `scripts/test_desktop.sh`; a full APK build needs the documented JDK, Android SDK/NDK, and Buildozer toolchain.

