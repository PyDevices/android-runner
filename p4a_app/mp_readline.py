# SPDX-License-Identifier: MIT
"""MicroPython-style line editor (port of shared/readline/readline.c)."""

from __future__ import annotations

CHAR_CTRL_A = 1
CHAR_CTRL_B = 2
CHAR_CTRL_C = 3
CHAR_CTRL_D = 4
CHAR_CTRL_E = 5
CHAR_CTRL_F = 6
CHAR_CTRL_K = 11
CHAR_CTRL_N = 14
CHAR_CTRL_P = 16
CHAR_CTRL_U = 21

ESEQ_NONE = 0
ESEQ_ESC = 1
ESEQ_ESC_BRACKET = 2
ESEQ_ESC_BRACKET_DIGIT = 3
ESEQ_ESC_O = 4

AUTO_INDENT_ENABLED = 0x01
AUTO_INDENT_JUST_ADDED = 0x02

DEFAULT_HISTORY_SIZE = 50


def _code(c) -> int:
    if isinstance(c, int):
        return c
    if not c:
        return -1
    return ord(c[0])


class Readline:
    def __init__(self, write, autocomplete=None, history_size=DEFAULT_HISTORY_SIZE):
        self._write = write
        self._autocomplete = autocomplete
        self.history_size = history_size
        self.history = [None] * history_size
        self.line = ""
        self.orig_line_len = 0
        self.cursor_pos = 0
        self.escape_seq = ESEQ_NONE
        self.escape_digit = ""
        self.hist_cur = -1
        self.last_nl = 0
        self.auto_indent_state = 0
        self.prompt = ""

    def push_history(self, line: str):
        if not line:
            return
        if self.history[0] is not None and self.history[0] == line:
            return
        for i in range(self.history_size - 1, 0, -1):
            self.history[i] = self.history[i - 1]
        self.history[0] = line

    def _move_back(self, pos: int):
        if pos <= 0:
            return
        if pos <= 4:
            self._write("\b" * pos)
        else:
            self._write("\x1b[%uD" % pos)

    def _erase_from_cursor(self):
        self._write("\x1b[K")

    def _process_nl(self, c: int) -> bool:
        if (c == 13 or c == 10) and (self.last_nl == 0 or self.last_nl == c):
            self.last_nl = c
            return True
        self.last_nl = 0
        return False

    def _cursor_count_word(self, forward: bool) -> int:
        buf = self.line
        pos = self.cursor_pos
        in_word = False
        while True:
            if not forward and pos == 0:
                break
            if forward and pos == len(buf):
                break
            ch = buf[pos - (0 if forward else 1)]
            if ch.isalnum() or ch == "_":
                in_word = True
            elif in_word:
                break
            pos += 1 if forward else -1
        return (pos - self.cursor_pos) if forward else (self.cursor_pos - pos)

    def _auto_indent(self):
        if not (self.auto_indent_state & AUTO_INDENT_ENABLED):
            return
        line = self.line
        if len(line) > 1 and line[-1] == "\n":
            i = len(line) - 1
            while i > 0 and line[i - 1] != "\n":
                i -= 1
            j = i
            while j < len(line) and line[j] == " ":
                j += 1
            if i > 0 and j + 1 == len(line):
                for k in range(i - 1, 0, -1):
                    if line[k - 1] == "\n":
                        return
                    if line[k - 1] != " ":
                        break
            n = (j - i) // 4
            if len(line) >= 2 and line[-2] == ":":
                n += 1
            while n > 0:
                self.line += "    "
                self._write("    ")
                self.cursor_pos += 4
                self.auto_indent_state |= AUTO_INDENT_JUST_ADDED
                n -= 1

    def init(self, prompt: str, existing: str = ""):
        self.line = existing
        self.orig_line_len = len(existing)
        self.escape_seq = ESEQ_NONE
        self.escape_digit = ""
        self.hist_cur = -1
        self.cursor_pos = len(existing)
        self.prompt = prompt
        self._write(prompt)
        if len(existing) == 0:
            self.auto_indent_state = AUTO_INDENT_ENABLED
        self._auto_indent()

    def note_newline(self, prompt: str):
        self.orig_line_len = len(self.line)
        self.cursor_pos = self.orig_line_len
        self.prompt = prompt
        self._write(prompt)
        self._auto_indent()

    def current_input(self) -> str:
        return self.line[self.orig_line_len :]

    def process_char(self, c) -> int:
        """Return -1 to continue, 0 on newline, or CHAR_CTRL_* (1..5) on blank-line control."""
        c = _code(c)
        if c < 0:
            return -1
        last_line_len = len(self.line)
        redraw_step_back = 0
        redraw_from_cursor = False
        redraw_step_forward = 0

        if self.escape_seq == ESEQ_NONE:
            if CHAR_CTRL_A <= c <= CHAR_CTRL_E and len(self.line) == self.orig_line_len:
                return c
            if c == CHAR_CTRL_A:
                redraw_step_back = self.cursor_pos - self.orig_line_len
            elif c == CHAR_CTRL_B:
                if self.cursor_pos > self.orig_line_len:
                    redraw_step_back = 1
            elif c == CHAR_CTRL_C:
                return c
            elif c == CHAR_CTRL_D:
                if self.cursor_pos < len(self.line):
                    self.line = (
                        self.line[: self.cursor_pos] + self.line[self.cursor_pos + 1 :]
                    )
                    redraw_from_cursor = True
                else:
                    return c
            elif c == CHAR_CTRL_E:
                redraw_step_forward = len(self.line) - self.cursor_pos
            elif c == CHAR_CTRL_F:
                if self.cursor_pos < len(self.line):
                    redraw_step_forward = 1
            elif c == CHAR_CTRL_K:
                self.line = self.line[: self.cursor_pos]
                redraw_from_cursor = True
            elif c == CHAR_CTRL_N:
                # down history
                if self.hist_cur >= 0:
                    self.hist_cur -= 1
                    self.line = self.line[: self.orig_line_len]
                    if self.hist_cur >= 0 and self.history[self.hist_cur]:
                        self.line += self.history[self.hist_cur]
                    redraw_step_back = self.cursor_pos - self.orig_line_len
                    redraw_from_cursor = True
                    redraw_step_forward = len(self.line) - self.orig_line_len
            elif c == CHAR_CTRL_P:
                if (
                    self.hist_cur + 1 < self.history_size
                    and self.history[self.hist_cur + 1] is not None
                ):
                    self.hist_cur += 1
                    self.line = self.line[: self.orig_line_len] + self.history[self.hist_cur]
                    redraw_step_back = self.cursor_pos - self.orig_line_len
                    redraw_from_cursor = True
                    redraw_step_forward = len(self.line) - self.orig_line_len
            elif c == CHAR_CTRL_U:
                cut = self.cursor_pos - self.orig_line_len
                self.line = self.line[: self.orig_line_len] + self.line[self.cursor_pos :]
                redraw_step_back = cut
                redraw_from_cursor = True
            elif self._process_nl(c):
                self._write("\r\n")
                self.push_history(self.current_input())
                return 0
            elif c == 27:
                self.escape_seq = ESEQ_ESC
            elif c in (8, 127):
                if self.cursor_pos > self.orig_line_len:
                    nspace = 1
                    # backspace over auto-indent groups of 4
                    nspace_count = 0
                    for i in range(self.orig_line_len, self.cursor_pos):
                        if self.line[i] != " ":
                            nspace_count = 0
                            break
                        nspace_count += 1
                    if 0 < nspace_count and nspace_count >= 4:
                        nspace = 4
                    elif nspace_count:
                        nspace = nspace_count if nspace_count < 4 else 1
                    self.line = (
                        self.line[: self.cursor_pos - nspace]
                        + self.line[self.cursor_pos :]
                    )
                    redraw_step_back = nspace
                    redraw_from_cursor = True
            elif (self.auto_indent_state & AUTO_INDENT_JUST_ADDED) and c in (9, 32):
                self.auto_indent_state = 0
                if c == 32:
                    redraw_step_back = 3
                    self.line = self.line[:-3]
            elif c == 9:
                # tab
                if self.cursor_pos > 0 and self.line[self.cursor_pos - 1].isspace():
                    compl_str, compl_len = "    ", 4
                elif self._autocomplete is not None:
                    before = self.line[self.orig_line_len : self.cursor_pos]
                    compl_str, compl_len = self._autocomplete(before)
                else:
                    compl_str, compl_len = "", 0
                if compl_len == 0:
                    pass
                elif compl_len == -1:
                    self._write(self.prompt)
                    self._write(self.line[self.orig_line_len : self.cursor_pos])
                    redraw_from_cursor = True
                else:
                    self.line = (
                        self.line[: self.cursor_pos]
                        + compl_str[:compl_len]
                        + self.line[self.cursor_pos :]
                    )
                    redraw_from_cursor = True
                    redraw_step_forward = compl_len
            elif 32 <= c <= 126:
                self.line = (
                    self.line[: self.cursor_pos]
                    + chr(c)
                    + self.line[self.cursor_pos :]
                )
                redraw_from_cursor = True
                redraw_step_forward = 1
        elif self.escape_seq == ESEQ_ESC:
            if c == ord("["):
                self.escape_seq = ESEQ_ESC_BRACKET
            elif c == ord("O"):
                self.escape_seq = ESEQ_ESC_O
            elif c == ord("b"):
                redraw_step_back = self._cursor_count_word(False)
                self.escape_seq = ESEQ_NONE
            elif c == ord("f"):
                redraw_step_forward = self._cursor_count_word(True)
                self.escape_seq = ESEQ_NONE
            elif c == ord("d"):
                n = self._cursor_count_word(True)
                self.line = self.line[: self.cursor_pos] + self.line[self.cursor_pos + n :]
                redraw_from_cursor = True
                self.escape_seq = ESEQ_NONE
            elif c == 127:
                n = self._cursor_count_word(False)
                self.line = (
                    self.line[: self.cursor_pos - n] + self.line[self.cursor_pos :]
                )
                redraw_step_back = n
                redraw_from_cursor = True
                self.escape_seq = ESEQ_NONE
            else:
                self.escape_seq = ESEQ_NONE
        elif self.escape_seq == ESEQ_ESC_BRACKET:
            if ord("0") <= c <= ord("9"):
                self.escape_seq = ESEQ_ESC_BRACKET_DIGIT
                self.escape_digit = chr(c)
            else:
                self.escape_seq = ESEQ_NONE
                if c == ord("A"):  # up
                    if (
                        self.hist_cur + 1 < self.history_size
                        and self.history[self.hist_cur + 1] is not None
                    ):
                        self.hist_cur += 1
                        self.line = (
                            self.line[: self.orig_line_len] + self.history[self.hist_cur]
                        )
                        redraw_step_back = self.cursor_pos - self.orig_line_len
                        redraw_from_cursor = True
                        redraw_step_forward = len(self.line) - self.orig_line_len
                elif c == ord("B"):  # down
                    if self.hist_cur >= 0:
                        self.hist_cur -= 1
                        self.line = self.line[: self.orig_line_len]
                        if self.hist_cur >= 0 and self.history[self.hist_cur]:
                            self.line += self.history[self.hist_cur]
                        redraw_step_back = self.cursor_pos - self.orig_line_len
                        redraw_from_cursor = True
                        redraw_step_forward = len(self.line) - self.orig_line_len
                elif c == ord("C"):
                    if self.cursor_pos < len(self.line):
                        redraw_step_forward = 1
                elif c == ord("D"):
                    if self.cursor_pos > self.orig_line_len:
                        redraw_step_back = 1
                elif c == ord("H"):
                    redraw_step_back = self.cursor_pos - self.orig_line_len
                elif c == ord("F"):
                    redraw_step_forward = len(self.line) - self.cursor_pos
        elif self.escape_seq == ESEQ_ESC_BRACKET_DIGIT:
            if c == ord("~"):
                d = self.escape_digit
                if d in ("1", "7"):
                    redraw_step_back = self.cursor_pos - self.orig_line_len
                elif d in ("4", "8"):
                    redraw_step_forward = len(self.line) - self.cursor_pos
                elif d == "3":
                    if self.cursor_pos < len(self.line):
                        self.line = (
                            self.line[: self.cursor_pos]
                            + self.line[self.cursor_pos + 1 :]
                        )
                        redraw_from_cursor = True
            elif c == ord(";") and self.escape_digit == "1":
                self.escape_seq = ESEQ_ESC_BRACKET
                # fall through to redraw without resetting digit path below
                self._redraw(
                    last_line_len,
                    redraw_step_back,
                    redraw_from_cursor,
                    redraw_step_forward,
                )
                return -1
            elif self.escape_digit == "5" and c == ord("C"):
                redraw_step_forward = self._cursor_count_word(True)
            elif self.escape_digit == "5" and c == ord("D"):
                redraw_step_back = self._cursor_count_word(False)
            self.escape_seq = ESEQ_NONE
        elif self.escape_seq == ESEQ_ESC_O:
            if c == ord("H"):
                redraw_step_back = self.cursor_pos - self.orig_line_len
            elif c == ord("F"):
                redraw_step_forward = len(self.line) - self.cursor_pos
            self.escape_seq = ESEQ_NONE
        else:
            self.escape_seq = ESEQ_NONE

        self._redraw(
            last_line_len, redraw_step_back, redraw_from_cursor, redraw_step_forward
        )
        self.auto_indent_state &= ~AUTO_INDENT_JUST_ADDED
        return -1

    def _redraw(self, last_line_len, step_back, from_cursor, step_forward):
        if step_back > 0:
            self._move_back(step_back)
            self.cursor_pos -= step_back
        if from_cursor:
            if len(self.line) < last_line_len:
                self._erase_from_cursor()
            self._write(self.line[self.cursor_pos :])
            self._move_back(len(self.line) - (self.cursor_pos + step_forward))
            self.cursor_pos += step_forward
        elif step_forward > 0:
            self._write(self.line[self.cursor_pos : self.cursor_pos + step_forward])
            self.cursor_pos += step_forward
