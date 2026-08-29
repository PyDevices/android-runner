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

- **Interpreter:** CPython under [python-for-android](https://python-for-android.readthedocs.io/) with the SDL2 bootstrap.
- **Payload:** native LVGL and pygraphics wheels plus the complete PyDevices library stack.
- **Stdio bridge:** `p4a_app/stdio_sidecar.py` listens on `127.0.0.1:18765` so `android.py` can attach bidirectional terminal stdio and a MicroPython-style REPL.
- **Startup:** `boot.py` sets up environment, path layout, and the sidecar, then runs whatever `android.py` staged into `run/`.

## Building it yourself

```bash
./build_android.sh -y
```

Output: `p4a_app/bin/runner-0.1.0-arm64-v8a_x86_64-debug.apk`

`build_android.sh` tries to sync `p4a_app/utils/` from a sibling `../pydevices-examples` checkout (and `../pydevices` for `mip.py`): a clean standalone clone has no such siblings, so the sync is skipped and the checked-in `p4a_app/utils/` is used as-is, while a workspace checkout that has those repos as siblings gets freshly-synced helpers on every build — override either source with `PYDEVICES_EXAMPLES_UTILS` / `PYDEVICES_PRODUCT_ROOT`.

The build prerequisites, buildozer configuration, p4a recipes, and the
`getEntryPoint` patch are documented once, in
[android-template/docs/building.md](https://github.com/PyDevices/android-template/blob/main/docs/building.md) —
this repo used to carry a byte-identical copy.

> **Ownership:** this repo (android-runner) owns the shared build machinery —
> `build_android.sh`'s core, `p4a_recipes/`, and `scripts/`. android-template
> hand-syncs its copies from here; edit here first, then sync to the template.
> As of this writing `p4a_recipes/` and `scripts/` are byte-identical between
> the two repos (this repo additionally carries `scripts/android_stdio_attach.py`
> and `scripts/patch_p4a_boot_entrypoint.py`, which the template does not need).

## Toolchain

CI (`.github/workflows/release_apk.yml`) builds with:

| Tool | Version |
|------|---------|
| Python | 3.12 |
| JDK | 17 (temurin) |
| Android build-tools | 34.0.0 |
| Android NDK | 25.2.9519653 |
| Android platform | android-34 |

Match these locally for the closest build to CI's. `buildozer` and `python-for-android`
are **not** pinned here — `requirements-dev.txt` only floors `buildozer>=1.5.0`, and
buildozer resolves p4a itself (no `p4a.branch` / pip pin in `buildozer.spec`) — so a
local build and CI can still land on different buildozer/p4a versions even with the
table above matched. Do not describe builds from this repo as reproducible until
that gap is closed.

## Releases

GitHub Actions builds the multi-ABI (`arm64-v8a`, `x86_64`) debug APK on release
tags and publishes `pydevices-runner-debug.apk` to GitHub Releases, which is what
`android.py --install-apk` fetches.
