# SPDX-License-Identifier: MIT
"""MicroPython-style ``help`` / ``help('modules')`` / ``help(obj)``."""

from __future__ import annotations

import sys

_HELP_TEXT = """\
Welcome to PyDevices Android CPython!

Control commands:
  CTRL-A        -- on a blank line, enter raw REPL mode
  CTRL-B        -- on a blank line, enter normal REPL mode
  CTRL-C        -- interrupt a running program
  CTRL-D        -- on a blank line, soft reset
  CTRL-E        -- on a blank line, enter paste mode

Host attach: Ctrl-\\ disconnects the terminal (app keeps running).
For further help on a specific object, type help(obj)
"""

# Match MicroPython py/builtinhelp.c
NUM_COLUMNS = 4
COLUMN_WIDTH = 18


def _collect_module_names():
    """Top-level names only — same short column layout as MicroPython.

    CPython's ``pkgutil`` would otherwise dump every submodule
    (``asyncio.base_events``, …) and blow the 18-char columns.
    """
    builtins = set(sys.builtin_module_names)
    names = set(builtins)
    for name in sys.modules:
        if name and "." not in name:
            names.add(name)
    try:
        import pkgutil

        for m in pkgutil.iter_modules():
            if m.name and "." not in m.name:
                names.add(m.name)
    except Exception:
        pass

    # MicroPython lists a few private builtins (``_thread``, ``_asyncio``).
    # CPython's builtin_module_names is full of ``_abc`` / ``_codecs_*`` noise —
    # keep only the MP-shaped private names plus ``__main__``.
    _private_ok = {"_thread", "_asyncio", "__main__"}
    out = []
    for n in names:
        if n.startswith("_") and n not in _private_ok:
            continue
        out.append(n)
    return sorted(out)


def _print_modules(write):
    items = _collect_module_names()
    if not items:
        return
    num_rows = (len(items) + NUM_COLUMNS - 1) // NUM_COLUMNS
    for i in range(num_rows):
        j = i
        while True:
            name = items[j]
            write(name)
            j += num_rows
            if j >= len(items):
                break
            gap = COLUMN_WIDTH - len(name)
            while gap < 1:
                gap += COLUMN_WIDTH
            write(" " * gap)
        write("\n")
    write("Plus any modules on the filesystem\n")


def _print_obj(write, obj):
    write("object ")
    write(repr(obj))
    write(" is of type %s\n" % type(obj).__name__)
    # Prefer type/module namespace listing like MicroPython.
    mapping = None
    if isinstance(obj, type):
        mapping = getattr(obj, "__dict__", None)
    elif isinstance(obj, type(sys)):
        mapping = getattr(obj, "__dict__", None)
    else:
        mapping = getattr(type(obj), "__dict__", None)
    if mapping is None:
        try:
            names = dir(obj)
        except Exception:
            return
        for name in names:
            if name.startswith("_"):
                continue
            try:
                val = getattr(obj, name)
            except Exception:
                continue
            write("  %s -- %r\n" % (name, val))
        return
    for name in sorted(mapping.keys()):
        if not isinstance(name, str) or name.startswith("_"):
            continue
        try:
            val = mapping[name]
        except Exception:
            continue
        write("  %s -- %r\n" % (name, val))


def make_help(write=None):
    """Return a ``help`` builtin. Uses ``sys.stdout.write`` if write is None."""

    def _write(s):
        if write is not None:
            write(s)
        else:
            sys.stdout.write(s)

    def help_fn(*args):
        if not args:
            _write(_HELP_TEXT)
            return None
        obj = args[0]
        if obj == "modules":
            _print_modules(_write)
            return None
        _print_obj(_write, obj)
        return None

    help_fn.__name__ = "help"
    help_fn.__doc__ = "MicroPython-style help"
    return help_fn
