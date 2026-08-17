[app]
title = PyDevices Runner
package.name = runner
package.domain = org.pydevices
source.dir = .
source.include_exts = py,xml
# p4a/sdl2 still requires a main.py in the private bundle. Runtime entry is
# boot.py via the getEntryPoint patch in build_android.sh (MicroPython-shaped).
source.main = main.py
# PyDevices logo (from PyDevices.github.io/assets/img/logo-512.png)
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/icon.png
version = 0.1.0
android.debuggable = 1
# Standalone LVGL launcher + baked TestPyPI stack. Native: pygraphics /
# pydevices-lvgl Android wheels. pydevices-desktop ships usdl2 + board_config;
# p4a sdl2 bootstrap provides libSDL2.so.
requirements = python3,sdl2,setuptools,pip,pyjnius,pydevices-events,pydevices-keys,pydevices-multimer,pydevices-displaydev,pydevices-audiodev,pydevices-eventsys,pydevices-pygraphics,pydevices-palettes,pydevices-pdwidgets,pydevices-desktop,pydeviceslvgl
# Both aspects allowed in the manifest; AndroidSDLDisplay then locks to fixed
# LANDSCAPE or PORTRAIT from logical size (tilt does nothing).
orientation = portrait,landscape
fullscreen = 0
# API 34+: FOREGROUND_SERVICE_MEDIA_PLAYBACK + typed FGS required for audio.
android.api = 34
android.minapi = 24
# Phones/TVs: arm64-v8a. PC AVD (Pixel 9 x86_64): x86_64. TestPyPI native
# wheels cover both; cibuildwheel has no armeabi_v7a.
android.archs = arm64-v8a,x86_64
# Prefer p4a.bootstrap (android.bootstrap is deprecated in newer buildozer).
p4a.bootstrap = sdl2
android.bootstrap = sdl2
# mediaPlayback FGS + notifications (Android 14+/17 AudioHardening).
android.permissions = INTERNET,FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PLAYBACK,POST_NOTIFICATIONS,WAKE_LOCK
# Keep-alive service so USAGE_MEDIA OpenSL is not silenced when hardened.
services = mediaplayback:./services/mediaplayback.py:foreground:foregroundServiceType=mediaPlayback
# Keep local SDK/NDK; do not re-run sdkmanager updates every build.
android.skip_update = True

# Why LEANBACK_LAUNCHER: Android TV / Fire OS launcher visibility (phone
# LAUNCHER filter remains from p4a defaults).
android.manifest.intent_filters = %(source.dir)s/intent_filters_tv.xml
# Why extra_manifest_xml: leanback + optional touchscreen uses-feature tags
# (android.features alone forces required=true).
android.extra_manifest_xml = %(source.dir)s/tv_features.xml

# PyDevices wheels on TestPyPI (unpinned recipes install latest matching wheel).
# TestPyPI primary; PyPI secondary for deps that exist only on production PyPI.
p4a.extra_args = --extra-index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/

# Thin PyProjectRecipe wrappers that install matching TestPyPI / PyPI wheels.
p4a.local_recipes = ../p4a_recipes

[buildozer]
log_level = 2
warn_on_root = 0
