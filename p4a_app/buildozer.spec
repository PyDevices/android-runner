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
version = 0.2.9.dev5
# Android's versionCode. python-for-android derives it from a numeric version
# as 10, then android.minapi, then two digits per part (0.2.8 is 1024208), and
# refuses a dev or rc suffix. A dev or rc build takes its final's code, so the
# final installs over it. The release workflow checks this line against
# `version` before it builds.
android.numeric_version = 1024209
android.debuggable = 1
# Standalone LVGL launcher + baked PyPI stack. Native: pygraphics /
# omnipython-lvgl Android wheels. omnipython-desktop ships usdl2 + board_config;
# p4a sdl2 bootstrap provides libSDL2.so. bleak (with the android module it
# asks permissions through) gives bledev a Bluetooth LE central.
requirements = python3,sdl2,setuptools,pip,pyjnius,android,bleak,numpy,omnipython,omnipython-audiodsp,omnipython-audioinstruments,omnipython-audioeffects,omnipython-pygraphics,omnipython-palettes,omnipython-pdwidgets,omnipython-desktop,omnipythonlvgl
# Both aspects allowed in the manifest; AndroidSDLDisplay then locks to fixed
# LANDSCAPE or PORTRAIT from logical size (tilt does nothing).
orientation = portrait,landscape
fullscreen = 0
# API 34+: FOREGROUND_SERVICE_MEDIA_PLAYBACK + typed FGS required for audio.
android.api = 34
android.minapi = 24
# Phones/TVs: arm64-v8a. PC AVD (Pixel 9 x86_64): x86_64. The PyPI native
# wheels cover both; cibuildwheel has no armeabi_v7a.
android.archs = arm64-v8a,x86_64
# Prefer p4a.bootstrap (android.bootstrap is deprecated in newer buildozer).
p4a.bootstrap = sdl2
android.bootstrap = sdl2
# mediaPlayback FGS + notifications (Android 14+/17 AudioHardening).
# Bluetooth LE as a central: SCAN and CONNECT from Android 12 (API 31); before
# that BLUETOOTH, BLUETOOTH_ADMIN and a location permission, which bleak asks
# for on every version. All are asked for at run time, when a program first
# opens the radio.
android.permissions = INTERNET,FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PLAYBACK,POST_NOTIFICATIONS,WAKE_LOCK,BLUETOOTH_SCAN,BLUETOOTH_CONNECT,(name=android.permission.BLUETOOTH;maxSdkVersion=30),(name=android.permission.BLUETOOTH_ADMIN;maxSdkVersion=30),ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION
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

# Thin PyProjectRecipe wrappers that install the pinned PyPI wheels.
p4a.local_recipes = ../p4a_recipes
# Patches the dist so the Activity starts boot.py and declares the Relauncher
# (see scripts/p4a_hook.py).
p4a.hook = ../scripts/p4a_hook.py
# Java beside p4a's: the Relauncher that gives a launcher button's example a
# process of its own (p4a_app/session.py).
android.add_src = ../p4a_java

[buildozer]
log_level = 2
warn_on_root = 0
