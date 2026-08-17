# Building APKs

Prerequisites: [Android SDK + NDK](https://python-for-android.readthedocs.io/en/latest/quickstart.html), Ubuntu/WSL build tools (`git`, `zip`, `openjdk-17-jdk`, `autoconf`, …). Tooling already downloaded by buildozer lives under `~/.buildozer/android/platform/` by default.

A practical workflow is to iterate on the app logic first, then only change the packaging layer when you need a new dependency or a different build setting. In most cases that means editing **`p4a_app/boot.py`** (startup / `PYDEVICES_*`), **`p4a_app/main.py`** / **`launcher.py`** (user entry), and **`p4a_app/buildozer.spec`** or **`p4a_recipes/`** when the APK’s runtime package list changes. Display wiring comes from TestPyPI **pydevices-desktop** (`board_config` + pure-Python `usdl2`); do not add a local `board_config.py` that shadows it.

```bash
./build_android.sh              # prompts for launcher title (Enter = current)
./build_android.sh -y           # keep current title (CI / automation)
./build_android.sh --title Paint
# APK: p4a_app/bin/launcher-0.5.0-*-debug.apk (name may vary)
./scripts/emulator.sh
```

`build_android.sh` creates `.venv/` and installs host deps from `requirements-dev.txt`. It rsyncs sibling `pydevices-examples/lib/utils/` into `p4a_app/utils/`, then overlays canonical `pydevices/utils/mip.py`. Override the sources with `PYDEVICES_EXAMPLES_UTILS` and `PYDEVICES_PRODUCT_ROOT`. Runtime distributions (**pydevices-displaydev**, **pydevices-desktop**, …) come from TestPyPI via `p4a_recipes/`. For local iteration only, pass `--local-modules` (or `ANDROID_DEBUG_LOCAL_MODULES=1`) to shadow the `displaydev/`, `usdl2.py`, and `audiodev/` imports from sibling checkouts into `p4a_app/`; default builds remove those shadows. Package id: **`org.pydevices.launcher`**. Launcher label comes from `title` in `p4a_app/buildozer.spec` (**PyDevices Launcher**).

`p4a_app/stdio_sidecar.py` (started from `boot.py`) listens on localhost so `scripts/android.sh` can attach this terminal as the app’s stdin/stdout/stderr, including `-i` for a MicroPython-style REPL. `build_android.sh` patches p4a’s `getEntryPoint` so the Activity runs `boot.py` before optional user `main.py` (upstream sdl2 otherwise hardcodes `main.py`).

## Icon and presplash

`buildozer.spec` points both at the same asset:

```ini
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/icon.png
```

| Spec | Details |
|------|---------|
| File | `p4a_app/icon.png` (default: copy of [PyDevices logo-512.png](https://github.com/PyDevices/PyDevices.github.io/blob/main/assets/img/logo-512.png)) |
| Format | PNG, square, RGBA preferred |
| Size | **512×512** (buildozer resizes into density buckets) |
| `icon` | Launcher / home-screen icon |
| `presplash` | Startup splash while Python/SDL bootstrap |

Replace `icon.png` (or change the paths) and rebuild for a new look.

## Desktop smoke test (Xvfb)

```bash
./scripts/test_desktop.sh
```

## Emulator / phone

```bash
./scripts/emulator.sh          # AVD already running (WSL → use Windows AVD + adb.exe)
./scripts/phone.sh             # USB-connected phone (skips emulators)
```

On WSL, start the AVD from **Windows** (Device Manager ▶), then talk to it with Windows `adb.exe` (e.g. a `~/bin/adb.exe` symlink to `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`).

### USB debugging on a Samsung phone (One UI)

USB debugging is hidden until Developer options are unlocked, and Samsung **Auto Blocker** can leave it greyed out (“blocked by auto blocker”).

1. **Settings → About phone → Software information** → tap **Build number** seven times (unlock Developer options).
2. If USB debugging says blocked by Auto Blocker:
   - **Settings → Security and privacy → Auto Blocker** → turn the **main switch off** (PIN/fingerprint if asked).
3. **Settings → Developer options** → enable **USB debugging** → OK.
4. Plug in a data USB cable; accept **Allow USB debugging?** on the phone.
5. Confirm from WSL: `adb.exe devices` shows a non-`emulator-*` line as `device`, then run `./scripts/phone.sh`.

You can turn Auto Blocker back on afterward; USB debugging may be blocked again until you disable it.

### Android SDK Command-line Tools (`sdkmanager`)

A Studio-installed SDK often has no `cmdline-tools/` folder until you add it. Without that package there is no `sdkmanager.bat` for CLI image installs.

1. Android Studio → **Settings → Languages & Frameworks → Android SDK → SDK Tools**
2. Check **Android SDK Command-line Tools (latest)** → Apply
3. The batch file lands at:

```text
%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\bin\sdkmanager.bat
```

From WSL that path is typically:

```text
/mnt/c/Users/<you>/AppData/Local/Android/Sdk/cmdline-tools/latest/bin/sdkmanager.bat
```

Example (AMD64 Windows — use an **x86_64** system image, not arm64):

```bat
"%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\bin\sdkmanager.bat" ^
  "system-images;android-37.1;google_apis_playstore_ps16k;x86_64"
```

An arm64 AVD on AMD64 Windows exits immediately (“emulator process for AVD … has terminated”). Until cmdline-tools are installed, download images from Studio’s Device Manager / SDK Manager UI instead.

## Your own app

Almost everything a user customizes for their APK lives under **`p4a_app/`**:

| Customize | Where |
|-----------|--------|
| Entry / demo code | `p4a_app/main.py`, `launcher.py` (or stage examples via `scripts/android.sh`); startup in `boot.py` |
| Display size / rotation / scale | `PYDEVICES_*` env in `boot.py` (or `board_config_tv.py` from `main.py` for TV) |
| Title, package id, orientation, version, permissions, `requirements` | `p4a_app/buildozer.spec` |
| Icon / presplash | `p4a_app/icon.png` (paths in the spec) |

Leave **`p4a_app/`** alone only when you need packaging or host tooling changes:

| Need | Where |
|------|--------|
| New / different CPython wheel install from TestPyPI | `p4a_recipes/` (+ list the recipe name in `buildozer.spec` `requirements`) |
| Build / install / smoke helpers | `build_android.sh`, `scripts/` |

Keep `p4a.local_recipes` pointed at this repo’s `p4a_recipes/` unless you are shipping your own recipe tree.
