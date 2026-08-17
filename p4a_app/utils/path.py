"""Portable, idempotent path configuration for PyDevices runtimes."""

import os
import sys

# Preferred search path directories in order
targets = [
    "",
    ".frozen",
    "lib",
    "utils",
    os.path.expanduser("~/.micropython/lib"),
]
if os.name != "nt":
    targets.append("/usr/lib/micropython")

insert_idx = 0
for t in targets:
    if t in ("", ".frozen"):
        if t not in sys.path:
            sys.path.insert(insert_idx, t)
            insert_idx += 1
        else:
            try:
                idx = sys.path.index(t)
                insert_idx = max(insert_idx, idx + 1)
            except ValueError:
                pass
    else:
        norm_t = os.path.normpath(t)
        found = False
        for idx, p in enumerate(sys.path):
            if p not in ("", ".frozen") and os.path.normpath(p) == norm_t:
                found = True
                insert_idx = max(insert_idx, idx + 1)
                break
        if not found:
            sys.path.insert(insert_idx, t)
            insert_idx += 1

