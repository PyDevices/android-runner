# Contributing

This repository builds the PyDevices Runner APK (`org.pydevices.runner`). Most
people never build it: `android.py --install-apk` installs the published one.
Build when you change the APK host, the recipes or the packaged payload. Bug
reports and fixes are welcome; open an
[issue](https://github.com/PyDevices/android-runner/issues) first for anything
larger than a fix.

## What is where

| Path | Purpose |
|---|---|
| `build_android.sh` | Creates the build environment, synchronizes helpers, and invokes Buildozer. |
| `p4a_app/boot.py` | Runtime setup and staged-program entrypoint. |
| `p4a_app/stdio_sidecar.py` | Loopback stdio and REPL bridge. |
| `p4a_app/main.py` and `launcher.py` | Bundled default home application. |
| `p4a_app/session.py` and `p4a_java/` | Runs a launcher button's example in a fresh process. |
| `p4a_recipes/` | python-for-android recipes for PyDevices packages. |
| `scripts/p4a_hook.py` and `scripts/patch_p4a_boot_entrypoint.py` | Patch the built dist so the Activity starts `boot.py`. |
| `scripts/test_desktop.sh` | Short desktop smoke of `boot.py` to `main.py`. |

[How the Runner starts a program](docs/how-it-works/index.md) explains how
those pieces run on the phone.

The APK carries CPython under
[python-for-android](https://python-for-android.readthedocs.io/) with the SDL2
bootstrap, native LVGL and pygraphics wheels, and the PyDevices library stack.
`boot.py` sets up the environment, the path layout and the sidecar, then runs
whatever `android.py` staged into `run/`.

## Try it on a desktop first

```bash
./scripts/test_desktop.sh
```

It makes a virtual environment, installs the PyDevices desktop packages from
TestPyPI, and runs `boot.py` and the launcher under Xvfb (`xvfb-run`) for a few
seconds, checking that a timer fires.

## Build the APK

```bash
./build_android.sh -y
```

The output is `p4a_app/bin/runner-<version>-arm64-v8a_x86_64-debug.apk`, where
the version comes from `p4a_app/buildozer.spec`. Older APKs stay in that
folder; the build lists only the one it just made. `build_android.sh --help`
lists the options.

Before it starts, the build drops any cached Python package (and the dist built
from it) whose version is not the pin in `p4a_recipes/`, so a moved pin always
reaches the APK. The compiled Python and SDL2 caches are kept, and the script
refuses `clean` and `distclean` unless `ALLOW_CLEAN=1` is set.

`build_android.sh` syncs `p4a_app/utils/` from a sibling `../pydevices-examples`
checkout, and `mip.py` from `../pydevices`. A standalone clone has no such
siblings, so the sync is skipped and the checked-in `p4a_app/utils/` is used.
Override either source with `PYDEVICES_EXAMPLES_UTILS` or
`PYDEVICES_PRODUCT_ROOT`.

Build prerequisites (the Android SDK and NDK, a JDK, Buildozer), the
Buildozer configuration, the recipes and the `getEntryPoint` patch are
described in [android-template's build guide](https://github.com/PyDevices/android-template/blob/main/docs/guides/build-an-apk.md).

### Toolchain

CI (`.github/workflows/release_apk.yml`) builds with:

| Tool | Version |
|------|---------|
| Python | 3.12 |
| JDK | 17 (temurin) |
| Android build-tools | 34.0.0 |
| Android NDK | 25.2.9519653 |
| Android platform | android-34 |

Match these locally for the closest build to CI's. Buildozer and
python-for-android are not pinned: `requirements-dev.txt` only floors
`buildozer>=1.5.0`, and Buildozer resolves p4a itself, so a local build and CI
can land on different versions even with the table matched. Builds from this
repository are not reproducible.

## Releases

Pushing a `v*` tag, or running the workflow by hand, makes GitHub Actions build
the multi-ABI (`arm64-v8a`, `x86_64`) debug APK and publish it to GitHub
Releases as `pydevices-runner-debug.apk`. That is the file
`android.py --install-apk` fetches.

## Shared build machinery

This repository owns `build_android.sh`'s core, `p4a_recipes/` and `scripts/`.
[android-template](https://github.com/PyDevices/android-template) keeps copies
of them: change them here first, then copy the change there. They are not all
identical: `scripts/install_apk_main.sh`, `p4a_hook.py` and `test_desktop.sh`
differ between the two, `android_stdio_attach.py` and
`patch_p4a_boot_entrypoint.py` exist only here, and `check_recipe_pins.py` only
in the template. Compare the trees before you copy.

## Docs

The pages are plain Markdown under `docs/`, starting at
[docs/index.md](docs/index.md). There is no docs build; check that links you add
resolve.
