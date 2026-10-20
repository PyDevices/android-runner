# SPDX-License-Identifier: MIT
"""Keep a build from packaging an older build's Python packages.

python-for-android reuses two things between builds: the per-arch install
directory (``build/python-installs/<dist>/<arch>``) and, when the recipe list is
unchanged, the whole dist (``dists/<dist>``, which holds the Python bundle that
ends up in the APK). Neither is refreshed when a recipe pin moves. Install a
newer ``pydevices`` over an older one and both ``*.dist-info`` directories
stay; move a pin back, or to any version that is already installed, and the
new pin is ignored. The APK then ships whatever was installed first.

``prune`` runs before the build and removes any package whose installed
versions are not exactly the recipe pin (the dist too, so its bundle is built
again). ``check`` runs from the p4a hook once the dist exists and fails the
build if a package is still wrong. Neither touches hostpython, python3, sdl2 or
any other cached compile.

    python3 scripts/stale_dist.py prune <platform dir> [recipes dir]
    python3 scripts/stale_dist.py check <dist dir> [recipes dir]
"""

import pathlib
import re
import shutil
import sys

_HERE = pathlib.Path(__file__).resolve().parent
RECIPES = _HERE.parent / "p4a_recipes"

# Recipes whose pip distribution is not named like the recipe.
_PIP_NAMES = {"pydeviceslvgl": "pydevices-lvgl"}


def norm(name):
    return re.sub(r"[-_.]+", "_", name).lower()


def pins(recipes=RECIPES):
    """{normalized pip name: pinned version} for every pinned recipe."""
    found = {}
    for init in sorted(pathlib.Path(recipes).glob("*/__init__.py")):
        text = init.read_text()
        name = re.search(r'^\s+name\s*=\s*"([^"]+)"', text, re.M)
        version = re.search(r'^\s+version\s*=\s*"([^"]+)"', text, re.M)
        if name and version:
            found[norm(_PIP_NAMES.get(name.group(1), name.group(1)))] = version.group(1)
    return found


def installed(site):
    """{normalized name: [versions]} from the *.dist-info directories in site."""
    found = {}
    for info in pathlib.Path(site).glob("*.dist-info"):
        name, _, version = info.name[: -len(".dist-info")].rpartition("-")
        found.setdefault(norm(name), []).append(version)
    return found


def problems(site, pinned):
    """Packages in site that are not exactly the pinned version."""
    out = []
    for name, versions in sorted(installed(site).items()):
        if name in pinned and versions != [pinned[name]]:
            out.append("%s: installed %s, pinned %s" % (name, ", ".join(sorted(versions)), pinned[name]))
    return out


def uninstall(site, name):
    """Remove every version of a package from site, using its RECORD."""
    site = pathlib.Path(site)
    for info in list(site.glob("*.dist-info")):
        if norm(info.name[: -len(".dist-info")].rpartition("-")[0]) != name:
            continue
        record = info / "RECORD"
        if record.is_file():
            for line in record.read_text().splitlines():
                rel = line.rsplit(",", 2)[0]
                target = site / rel
                if rel and (target.is_file() or target.is_symlink()):
                    target.unlink()
        shutil.rmtree(info)
    for directory in sorted((p for p in site.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
        if not any(directory.iterdir()):
            directory.rmdir()


def bundle_sites(dist):
    return sorted(pathlib.Path(dist).glob("_python_bundle__*/_python_bundle/site-packages"))


def prune(platform, recipes=RECIPES):
    pinned = pins(recipes)
    any_change = False
    for build in sorted(pathlib.Path(platform).glob("build-*")):
        changed = False
        for site in sorted(build.glob("build/python-installs/*/*")):
            for line in problems(site, pinned):
                name = line.split(":")[0]
                print("stale_dist: %s (%s)" % (line, site))
                uninstall(site, name)
                changed = True
                any_change = True
        for dist in sorted(build.glob("dists/*")):
            bad = [p for site in bundle_sites(dist) for p in problems(site, pinned)]
            if bad or changed:
                print("stale_dist: dropping dist %s so its bundle is built again" % dist)
                shutil.rmtree(dist)
    if not any_change:
        print("stale_dist: installed packages match the recipe pins")


def check(dist, recipes=RECIPES):
    pinned = pins(recipes)
    bad = [p for site in bundle_sites(dist) for p in problems(site, pinned)]
    if bad:
        raise RuntimeError(
            "dist %s carries packages that differ from the recipe pins:\n  %s" % (dist, "\n  ".join(bad))
        )
    return len(bundle_sites(dist))


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("prune", "check"):
        sys.exit(__doc__)
    recipes = sys.argv[3] if len(sys.argv) > 3 else RECIPES
    if sys.argv[1] == "prune":
        prune(sys.argv[2], recipes)
    else:
        check(sys.argv[2], recipes)
        print("stale_dist: dist packages match the recipe pins")
