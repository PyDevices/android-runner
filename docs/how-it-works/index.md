# How the Runner starts a program

android-runner builds the PyDevices Runner APK, the generic Android host used by the `android.py` command from [pydevices](https://github.com/PyDevices/pydevices).

[Install the Runner](../get-started/index.md) before you read on: this page is what happens after `android.py` has put a program on the phone.

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

A launcher button doesn't run its example inside the launcher. It restarts the Runner with the example as the entry, so the example gets a clean screen, and Back in it restarts the Runner into the launcher again. [`p4a_app/session.py`](https://github.com/PyDevices/android-runner/blob/main/p4a_app/session.py) explains how.
