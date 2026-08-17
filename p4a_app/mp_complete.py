# SPDX-License-Identifier: MIT
"""CPython adaptation of MicroPython ``mp_repl_autocomplete`` (py/repl.c)."""

from __future__ import annotations

import builtins
import keyword
import sys

WORD_SLOT_LEN = 16
MAX_LINE_LEN = 4 * WORD_SLOT_LEN


def _is_ident_char(c: str) -> bool:
    return c.isalnum() or c == "_"


def _module_names():
    names = set(sys.builtin_module_names)
    names.update(sys.modules.keys())
    try:
        import pkgutil

        for m in pkgutil.iter_modules():
            if m.name:
                names.add(m.name)
    except Exception:
        pass
    return sorted(names)


def _attr_names(obj):
    try:
        names = dir(obj)
    except Exception:
        names = []
    out = []
    for name in names:
        if not isinstance(name, str):
            continue
        try:
            getattr(obj, name)
        except Exception:
            continue
        out.append(name)
    return out


def _global_names(namespace: dict):
    names = set(namespace.keys())
    names.update(dir(builtins))
    names.update(keyword.kwlist)
    return sorted(names)


def _print_completions(write, prefix: str, matches: list[str]):
    line_len = MAX_LINE_LEN  # force newline for first word
    for d_str in matches:
        d_len = len(d_str)
        if not prefix and d_str.startswith("_"):
            continue
        gap = (line_len + WORD_SLOT_LEN - 1) // WORD_SLOT_LEN * WORD_SLOT_LEN - line_len
        if gap < 2:
            gap += WORD_SLOT_LEN
        if line_len + gap + d_len <= MAX_LINE_LEN:
            write(" " * gap)
            write(d_str)
            line_len += gap + d_len
        else:
            write("\n")
            write(d_str)
            line_len = d_len
    write("\n")


def _common_prefix(matches: list[str], start: int) -> int:
    if not matches:
        return start
    first = matches[0]
    limit = len(first)
    for m in matches[1:]:
        i = start
        while i < limit and i < len(m) and first[i] == m[i]:
            i += 1
        limit = i
    return limit


def autocomplete(text: str, namespace: dict, write) -> tuple[str, int]:
    """Return (suffix, n). n==0 none; n==-1 many (already printed); else insert n chars."""
    org = text
    top = len(text)
    # scan backwards for a.b.c chain
    s = top - 1
    start = 0
    while s >= 0:
        c = text[s]
        if not (_is_ident_char(c) or c == "."):
            start = s + 1
            break
        s -= 1
    else:
        start = 0

    chain = text[start:top]
    # resolve complete words before final partial
    parts = chain.split(".")
    if not parts:
        return "", 0

    obj = None  # None means globals / builtins / modules
    for word in parts[:-1]:
        if not word:
            return "", 0
        if obj is None:
            if word in namespace:
                obj = namespace[word]
            elif hasattr(builtins, word):
                obj = getattr(builtins, word)
            else:
                return "", 0
        else:
            try:
                obj = getattr(obj, word)
            except Exception:
                return "", 0

    partial = parts[-1]
    # after "import ", complete modules
    import_prefix = False
    if org.lstrip().startswith("import ") or org.lstrip().startswith("from "):
        # MicroPython: after exact "import " at start, obj=NULL → modules
        stripped = org
        if stripped.startswith("import "):
            rest = stripped[7:]
            if "." not in rest:
                import_prefix = True
                obj = None

    if import_prefix and "." not in chain:
        candidates = [m for m in _module_names() if m.startswith(partial)]
        if not partial:
            candidates = [m for m in candidates if not m.startswith("_")]
    elif obj is None and len(parts) == 1:
        candidates = [n for n in _global_names(namespace) if n.startswith(partial)]
        if not partial:
            candidates = [n for n in candidates if not n.startswith("_")]
    else:
        if obj is None:
            return "", 0
        candidates = [n for n in _attr_names(obj) if n.startswith(partial)]
        if not partial:
            candidates = [n for n in candidates if not n.startswith("_")]

    candidates = sorted(set(candidates))
    # Prefer statement form ``import `` (with trailing space), like MicroPython.
    import_str = "import "
    if (
        start == 0
        and len(parts) == 1
        and 0 < len(partial) < len(import_str)
        and import_str.startswith(partial)
    ):
        # Only if nothing better than the bare keyword / no other matches.
        others = [c for c in candidates if c != "import"]
        if not others:
            suffix = import_str[len(partial) :]
            return suffix, len(suffix)

    if not candidates:
        return "", 0

    match_len = _common_prefix(candidates, len(partial))
    if len(candidates) == 1 or match_len > len(partial):
        first = candidates[0]
        # if unique match, take full remainder
        if len(candidates) == 1:
            suffix = first[len(partial) :]
        else:
            suffix = first[len(partial) : match_len]
        return suffix, len(suffix)

    _print_completions(write, partial, candidates)
    return "", -1
