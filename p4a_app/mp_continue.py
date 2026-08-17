# SPDX-License-Identifier: MIT
"""Port of MicroPython ``mp_repl_continue_with_input`` (py/repl.c)."""

from __future__ import annotations


def _startswith_word(s: str, head: str) -> bool:
    if not s.startswith(head):
        return False
    n = len(head)
    return n == len(s) or not (s[n].isalnum() or s[n] == "_")


def continue_with_input(text: str) -> bool:
    """Return True if more input is needed before execution (MicroPython rules)."""
    if not text:
        return False

    starts_compound = text[0] == "@" or any(
        _startswith_word(text, kw)
        for kw in ("if", "while", "for", "try", "with", "def", "class", "async")
    )

    Q_NONE, Q_1_SINGLE, Q_1_DOUBLE, Q_3_SINGLE, Q_3_DOUBLE = 0, 1, 2, 3, 4
    n_paren = n_brack = n_brace = 0
    in_quote = Q_NONE
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "'":
            if (in_quote in (Q_NONE, Q_3_SINGLE)) and text[i : i + 3] == "'''":
                i += 2
                in_quote = Q_3_SINGLE - in_quote
            elif in_quote in (Q_NONE, Q_1_SINGLE):
                in_quote = Q_1_SINGLE - in_quote
        elif ch == '"':
            if (in_quote in (Q_NONE, Q_3_DOUBLE)) and text[i : i + 3] == '"""':
                i += 2
                in_quote = Q_3_DOUBLE - in_quote
            elif in_quote in (Q_NONE, Q_1_DOUBLE):
                in_quote = Q_1_DOUBLE - in_quote
        elif ch == "\\" and i + 1 < n and text[i + 1] in ("'", '"', "\\"):
            if in_quote != Q_NONE:
                i += 1
        elif in_quote == Q_NONE:
            if ch == "(":
                n_paren += 1
            elif ch == ")":
                n_paren -= 1
            elif ch == "[":
                n_brack += 1
            elif ch == "]":
                n_brack -= 1
            elif ch == "{":
                n_brace += 1
            elif ch == "}":
                n_brace -= 1
        i += 1

    if in_quote in (Q_3_SINGLE, Q_3_DOUBLE):
        return True
    if (n_paren > 0 or n_brack > 0 or n_brace > 0) and in_quote == Q_NONE:
        return True
    if text[-1] == "\\":
        return True
    if starts_compound and text[-1] != "\n":
        return True
    return False
