#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Patch p4a PythonActivity.getEntryPoint to prefer boot.py over main.py.

Upstream sdl2 hardcodes main.py/main.pyc. PyDevices uses MicroPython-shaped
boot.py (setup) + optional main.py (user code).
"""

from __future__ import annotations

import pathlib
import re
import sys

NEW_METHOD = """
    public String getEntryPoint(String search_dir) {
        /* PyDevices: MicroPython-shaped boot.py, then main.py (user code). */
        List<String> entryPoints = new ArrayList<String>();
        entryPoints.add("boot.pyc");
        entryPoints.add("boot.py");
        entryPoints.add("main.pyc"); // python 3 compiled files
        entryPoints.add("main.py");
        for (String value : entryPoints) {
            File mainFile = new File(search_dir + "/" + value);
            if (mainFile.exists()) {
                return value;
            }
        }
        return "boot.py";
    }
""".strip(
    "\n"
)

METHOD_RE = re.compile(
    r"    public String getEntryPoint\(String search_dir\) \{.*?\n    \}",
    re.DOTALL,
)


def patch_file(path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "entryPoints.add(\"boot.pyc\")" in text or "entryPoints.add(\"boot.py\")" in text:
        return "already"
    if not METHOD_RE.search(text):
        return "no-match"
    path.write_text(METHOD_RE.sub(NEW_METHOD, text, count=1), encoding="utf-8")
    return "patched"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: patch_p4a_boot_entrypoint.py <PythonActivity.java> [...]", file=sys.stderr)
        return 2
    rc = 0
    for raw in argv[1:]:
        path = pathlib.Path(raw)
        if not path.is_file():
            print(f"skip missing: {path}", file=sys.stderr)
            continue
        status = patch_file(path)
        print(f"{status}: {path}")
        if status == "no-match":
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
