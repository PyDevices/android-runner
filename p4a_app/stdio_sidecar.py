# SPDX-License-Identifier: MIT
"""Localhost stdio bridge for ``android.sh`` attach / MicroPython-like REPL.

Listens on ``127.0.0.1`` (default port 18765). When the host connects over
``adb forward``, redirects ``sys.stdin`` / ``stdout`` / ``stderr`` to that
socket (teeing writes to the previous streams so logcat still sees them).

Handshake: first line from the client is ``MODE=stdio`` or ``MODE=repl``.

``MODE=repl`` attaches stdio immediately, then runs a MicroPython-style
console **after** the staged ``run_entry`` returns (``python -i`` style).
With ``multimer`` threading there is no soft-IRQ preemption, so ``>>>``
does not appear while a long-running entry is still on the main thread.

  CTRL-A  -- on a blank line, enter raw REPL mode
  CTRL-B  -- on a blank line, enter normal REPL mode
  CTRL-C  -- interrupt a running program
  CTRL-D  -- on a blank line, soft reset (fresh namespace)
  CTRL-E  -- on a blank line, enter paste mode
"""

from __future__ import annotations

import codeop
import ctypes
import os
import queue
import socket
import sys
import threading
import time
import time as _time_mod
import traceback

DEFAULT_PORT = 18765
_HOST = "127.0.0.1"

_started = False
_lock = threading.Lock()
_client_busy = False
# Cleared until boot.py finishes user main.py / run_entry (or there is none).
_entry_done = threading.Event()

CHAR_CTRL_A = "\x01"
CHAR_CTRL_B = "\x02"
CHAR_CTRL_C = "\x03"
CHAR_CTRL_D = "\x04"
CHAR_CTRL_E = "\x05"


def _log_exc(where, exc=None):
    """Unexpected-failure sink (logcat / process stderr). Not for hot-path I/O."""
    try:
        err = sys.__stderr__
    except Exception:
        err = None
    if err is None:
        err = sys.stderr
    try:
        if exc is not None:
            err.write("stdio_sidecar: %s: %s\n" % (where, exc))
            traceback.print_exception(
                type(exc), exc, getattr(exc, "__traceback__", None), file=err
            )
        else:
            err.write("stdio_sidecar: %s\n" % (where,))
            traceback.print_exc(file=err)
        err.flush()
    except Exception:
        try:
            print("stdio_sidecar:", where, exc, flush=True)
        except Exception:
            pass


def log_exc(where, exc=None):
    """Public alias for :func:`_log_exc` (e.g. ``boot.py``)."""
    _log_exc(where, exc)


_prev_thread_excepthook = None
_thread_hook_installed = False


def _thread_excepthook(args):
    """Log deaths of stdio_* daemon threads; defer others to the previous hook."""
    thread = getattr(args, "thread", None)
    name = getattr(thread, "name", "") or ""
    if name.startswith("stdio"):
        if args.exc_type is SystemExit:
            return
        _log_exc("thread %s" % name, args.exc_value)
        return
    prev = _prev_thread_excepthook
    if prev is not None:
        prev(args)
    else:
        sys.__excepthook__(args.exc_type, args.exc_value, args.exc_traceback)


def _install_thread_excepthook():
    global _prev_thread_excepthook, _thread_hook_installed
    if _thread_hook_installed:
        return
    _thread_hook_installed = True
    _prev_thread_excepthook = getattr(threading, "excepthook", None)
    threading.excepthook = _thread_excepthook


def _async_raise(thread_ident, exc=KeyboardInterrupt):
    """Raise *exc* in another thread (best-effort; CPython)."""
    if not thread_ident:
        return False
    try:
        set_exc = ctypes.pythonapi.PyThreadState_SetAsyncExc
        set_exc.restype = ctypes.c_int
        for id_type in (ctypes.c_ulong, ctypes.c_long):
            set_exc.argtypes = (id_type, ctypes.py_object)
            try:
                n = int(set_exc(id_type(thread_ident), exc))
            except Exception:
                continue
            if n == 0:
                continue
            if n > 1:
                set_exc(id_type(thread_ident), None)
                return False
            return True
    except Exception:
        return False
    return False


class _TeeTextIO:
    """Text write stream that mirrors to a secondary stream (Android log)."""

    def __init__(self, primary_write, secondary, encoding="utf-8"):
        self._primary_write = primary_write
        self._secondary = secondary
        self._encoding = encoding

    def write(self, data):
        if not isinstance(data, str):
            data = str(data)
        try:
            self._primary_write(data)
        except Exception:
            pass
        if self._secondary is not None:
            try:
                self._secondary.write(data)
                self._secondary.flush()
            except Exception:
                pass
        return len(data)

    def flush(self):
        if self._secondary is not None:
            try:
                self._secondary.flush()
            except Exception:
                pass

    def isatty(self):
        return True

    @property
    def encoding(self):
        return self._encoding

    @property
    def closed(self):
        return False


class _BridgeStdin:
    """Line-oriented stdin for MODE=stdio (``\\x03`` → KeyboardInterrupt)."""

    def __init__(self, bridge):
        self._bridge = bridge
        self._buf = ""

    def readline(self, size=-1):
        while "\n" not in self._buf:
            if size == 0:
                return ""
            if self._bridge.interrupt_requested:
                self._bridge.interrupt_requested = False
                raise KeyboardInterrupt
            try:
                item = self._bridge.in_q.get(timeout=0.05)
            except queue.Empty:
                continue
            if item is None:
                line = self._buf
                self._buf = ""
                return line
            if item == CHAR_CTRL_C:
                self._bridge.interrupt_requested = False
                raise KeyboardInterrupt
            self._buf += item
            if size is not None and size > 0 and len(self._buf) >= size:
                break
        if size is not None and size > 0:
            line = self._buf[:size]
            self._buf = self._buf[size:]
            return line
        idx = self._buf.find("\n") + 1
        line = self._buf[:idx]
        self._buf = self._buf[idx:]
        return line

    def read(self, size=-1):
        if size == 0:
            return ""
        if size is None or size < 0:
            chunks = [self._buf]
            self._buf = ""
            while True:
                try:
                    item = self._bridge.in_q.get(timeout=0.05)
                except queue.Empty:
                    continue
                if item is None:
                    break
                chunks.append(item)
            return "".join(chunks)
        while len(self._buf) < size:
            try:
                item = self._bridge.in_q.get(timeout=0.05)
            except queue.Empty:
                continue
            if item is None:
                break
            self._buf += item
        out = self._buf[:size]
        self._buf = self._buf[size:]
        return out

    def isatty(self):
        return True

    @property
    def encoding(self):
        return "utf-8"

    @property
    def closed(self):
        return self._bridge.closed

    def fileno(self):
        raise OSError("stdio bridge has no fileno")


class _SocketBridge:
    """Owns the client socket: pump thread, stdin queue, stdout writes."""

    def __init__(self, conn):
        self.conn = conn
        self.in_q = queue.Queue()
        self._pending = ""  # leftover chars from a multi-char queue item
        self.closed = False
        self.interrupt_ident = None
        self.interrupt_requested = False
        # repl_active: MODE=repl owns the prompt (entry finished).
        # executing: run_source/_run_code in progress on the REPL thread.
        self.repl_active = False
        self.executing = False
        self._pump_thread = None
        self._write_lock = threading.Lock()
        self._decoder = __import__("codecs").getincrementaldecoder("utf-8")(
            "replace"
        )

    def start(self):
        self._pump_thread = threading.Thread(
            target=self._pump, name="stdio_bridge_pump", daemon=True
        )
        self._pump_thread.start()

    def write_text(self, data):
        if not data or self.closed:
            return
        # MicroPython uses CRLF on wire often; we keep LF and let the host TTY
        # render. Convert lone \\n to \\r\\n for raw TTY comfort.
        if isinstance(data, str):
            data = data.replace("\r\n", "\n").replace("\n", "\r\n")
            raw = data.encode("utf-8")
        else:
            raw = data
        with self._write_lock:
            try:
                self.conn.sendall(raw)
            except Exception:
                pass

    def interrupt(self):
        """Ctrl-C: interrupt running code (REPL and/or staged entry on main)."""
        self.interrupt_requested = True
        targets = []
        if self.interrupt_ident:
            targets.append(self.interrupt_ident)
        # After the REPL owns the prompt, do not poke the main/SDL thread —
        # that races multimer's time.sleep and can tear down the process.
        if not self.repl_active:
            try:
                main_id = threading.main_thread().ident
                if main_id and main_id not in targets:
                    targets.append(main_id)
            except Exception:
                pass
        any_ok = False
        for tid in targets:
            if _async_raise(tid, KeyboardInterrupt):
                any_ok = True
        if not any_ok:
            try:
                self.in_q.put(CHAR_CTRL_C)
            except Exception:
                pass

    def _pump(self):
        try:
            while not self.closed:
                try:
                    chunk = self.conn.recv(4096)
                except Exception:
                    break
                if not chunk:
                    break
                # Deliver control bytes as 1-char strings (not via UTF-8 decoder).
                out = []
                i = 0
                while i < len(chunk):
                    b = chunk[i]
                    if b == 3:
                        # Idle REPL: queue Ctrl-C in-order with preceding text
                        # in this chunk (so "zzz\\x03" cancels zzz, not a bare
                        # prompt followed by stray zzz).
                        # Running code / pre-REPL: flush text then interrupt.
                        if self.executing or not self.repl_active:
                            for part in out:
                                self.in_q.put(part)
                            out.clear()
                            self.interrupt()
                        else:
                            out.append(CHAR_CTRL_C)
                        i += 1
                        continue
                    if b in (1, 2, 4, 5):
                        out.append(chr(b))
                        i += 1
                        continue
                    j = i
                    while j < len(chunk) and chunk[j] not in (1, 2, 3, 4, 5):
                        j += 1
                    text = self._decoder.decode(chunk[i:j])
                    if text:
                        out.append(text)
                    i = j
                for part in out:
                    self.in_q.put(part)
        except Exception as exc:
            _log_exc("bridge pump", exc)
        finally:
            try:
                self.in_q.put(None)
            except Exception:
                pass
            self.closed = True

    def wait_closed(self):
        while not self.closed:
            time.sleep(0.05)

    def close(self):
        self.closed = True
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.conn.close()
        except Exception:
            pass

    def get_char(self, timeout=0.05):
        """Return next character, '' for timeout, None for EOF.

        Remainder of a multi-char chunk is kept in ``_pending`` (not re-queued)
        so a following control byte cannot jump ahead of the rest of the text.
        """
        if self._pending:
            ch, self._pending = self._pending[0], self._pending[1:]
            return ch
        try:
            item = self.in_q.get(timeout=timeout)
        except queue.Empty:
            return ""
        if item is None:
            return None
        if len(item) > 1:
            self._pending = item[1:]
            return item[0]
        return item


def _port():
    raw = os.environ.get("PYDEVICES_ANDROID_REPL_PORT", "").strip()
    if raw.isdigit():
        return int(raw)
    return DEFAULT_PORT


def _read_mode_line(bridge, timeout_s=5.0):
    """Read first line from the bridge queue as MODE=… handshake."""
    buf = ""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if "\n" in buf or "\r" in buf:
            break
        try:
            item = bridge.in_q.get(timeout=0.05)
        except queue.Empty:
            continue
        if item is None:
            break
        buf += item
    for sep in ("\n", "\r"):
        if sep in buf:
            line, _, rest = buf.partition(sep)
            # Drop paired LF after CR.
            if sep == "\r" and rest.startswith("\n"):
                rest = rest[1:]
            if rest:
                bridge.in_q.put(rest)
            buf = line
            break
    text = buf.strip()
    if text.startswith("MODE="):
        mode = text.split("=", 1)[1].strip().lower()
        if mode in ("stdio", "repl"):
            return mode
    return "stdio"


def _banner():
    ver = "%s.%s.%s" % sys.version_info[:3]
    return "PyDevices Android CPython %s\n" % ver


def _fresh_ns(write=None):
    import mp_help

    ns = {"__name__": "__console__", "__doc__": None}
    ns["help"] = mp_help.make_help(write)
    return ns


def _run_code(source, ns, filename="<stdin>", mode="single", bridge=None):
    """Compile and run. Returns True if more input is needed (compile_command)."""
    try:
        if mode == "single":
            cmd = codeop.compile_command(source, filename, "single")
            if cmd is None:
                return True
        else:
            cmd = compile(source, filename, "exec")
    except (OverflowError, SyntaxError, ValueError):
        traceback.print_exc()
        return False
    try:
        exec(cmd, ns)  # noqa: S102 -- REPL
    except SystemExit:
        raise
    except KeyboardInterrupt:
        if bridge is not None:
            bridge.interrupt_requested = False
        sys.stdout.write("\nKeyboardInterrupt\n")
    except Exception:
        traceback.print_exc()
    return False


def _run_mp_repl(bridge):
    """MicroPython-style friendly / raw / paste REPL on *bridge*."""
    import mp_complete
    import mp_continue
    import mp_readline

    write = bridge.write_text
    ns = _fresh_ns(write)
    mode_raw = False
    paste_mode = False
    raw_line = []

    def _auto(before: str):
        return mp_complete.autocomplete(before, ns, write)

    rl = mp_readline.Readline(write, autocomplete=_auto, history_size=50)

    def soft_reset():
        nonlocal ns, mode_raw, paste_mode, raw_line
        ns = _fresh_ns(write)
        mode_raw = False
        paste_mode = False
        raw_line = []
        bridge.interrupt_requested = False
        write("PyDevices: soft reboot\n")
        write(_banner())
        write('Type "help()" for more information.\n')
        rl.init(">>> ")

    def run_source(source: str):
        nonlocal ns
        bridge.executing = True
        bridge.interrupt_requested = False
        try:
            _run_code(source, ns, mode="single", bridge=bridge)
        except SystemExit:
            soft_reset()
            return
        finally:
            bridge.executing = False
            bridge.interrupt_requested = False
        rl.init(">>> ")

    bridge.repl_active = True
    write(_banner())
    write('Type "help()" for more information.\n')
    rl.init(">>> ")

    while not bridge.closed:
        try:
            try:
                ch = bridge.get_char(0.05)
            except KeyboardInterrupt:
                bridge.interrupt_requested = False
                write("\r\n")
                paste_mode = False
                mode_raw = False
                rl.init(">>> ")
                continue
            if ch is None:
                break
            if ch == "":
                if bridge.interrupt_requested and not mode_raw and not paste_mode:
                    bridge.interrupt_requested = False
                    write("\nKeyboardInterrupt\n")
                    paste_mode = False
                    rl.init(">>> ")
                continue

            # --- raw REPL -------------------------------------------------
            if mode_raw:
                if ch == CHAR_CTRL_A:
                    write("raw REPL; CTRL-B to exit\r\n>")
                    raw_line = []
                    continue
                if ch == CHAR_CTRL_B:
                    write("\r\n")
                    mode_raw = False
                    paste_mode = False
                    raw_line = []
                    write(_banner())
                    write('Type "help()" for more information.\n')
                    rl.init(">>> ")
                    continue
                if ch == CHAR_CTRL_C:
                    raw_line = []
                    bridge.interrupt_requested = False
                    continue
                if ch == CHAR_CTRL_D:
                    write("OK")
                    source = "".join(raw_line)
                    raw_line = []
                    if not source:
                        write("\r\n")
                        soft_reset()
                        continue
                    bridge.executing = True
                    try:
                        _run_code(
                            source, ns, filename="<stdin>", mode="exec", bridge=bridge
                        )
                    except SystemExit:
                        soft_reset()
                        continue
                    finally:
                        bridge.executing = False
                        bridge.interrupt_requested = False
                    write("\x04")
                    write("\x04")
                    write(">")
                    continue
                if ch in ("\r", "\n"):
                    raw_line.append("\n")
                else:
                    raw_line.append(ch)
                continue

            # --- paste mode -----------------------------------------------
            if paste_mode:
                if ch == CHAR_CTRL_C:
                    write("\r\n")
                    bridge.interrupt_requested = False
                    paste_mode = False
                    raw_line = []
                    rl.init(">>> ")
                    continue
                if ch == CHAR_CTRL_D:
                    write("\r\n")
                    source = "".join(raw_line)
                    raw_line = []
                    paste_mode = False
                    if source.strip():
                        bridge.executing = True
                        try:
                            _run_code(
                                source,
                                ns,
                                filename="<paste>",
                                mode="exec",
                                bridge=bridge,
                            )
                        except SystemExit:
                            soft_reset()
                            continue
                        finally:
                            bridge.executing = False
                            bridge.interrupt_requested = False
                    rl.init(">>> ")
                    continue
                if ch in ("\r", "\n"):
                    raw_line.append("\n")
                    write("\r\n=== ")
                else:
                    raw_line.append(ch)
                    write(ch)
                continue

            # --- friendly REPL (MicroPython readline) ---------------------
            ret = rl.process_char(ch)
            if ret < 0:
                continue
            if ret == 0:
                source = rl.line
                need_more = mp_continue.continue_with_input(source)
                if not need_more:
                    try:
                        cmd = codeop.compile_command(source, "<stdin>", "single")
                        need_more = cmd is None
                    except (OverflowError, SyntaxError, ValueError):
                        traceback.print_exc()
                        rl.init(">>> ")
                        continue
                if need_more:
                    if not source.endswith("\n"):
                        rl.line = source + "\n"
                    rl.note_newline("... ")
                else:
                    run_source(source)
                continue
            if ret == mp_readline.CHAR_CTRL_A:
                write("\r\n")
                mode_raw = True
                write("raw REPL; CTRL-B to exit\r\n>")
                raw_line = []
                continue
            if ret == mp_readline.CHAR_CTRL_B:
                write("\r\n")
                write(_banner())
                write('Type "help()" for more information.\n')
                rl.init(">>> ")
                continue
            if ret == mp_readline.CHAR_CTRL_C:
                write("\r\n")
                bridge.interrupt_requested = False
                rl.init(">>> ")
                continue
            if ret == mp_readline.CHAR_CTRL_D:
                if rl.orig_line_len > 0:
                    run_source(rl.line)
                else:
                    write("\r\n")
                    soft_reset()
                continue
            if ret == mp_readline.CHAR_CTRL_E:
                write("\r\npaste mode; Ctrl-C to cancel, Ctrl-D to finish\r\n=== ")
                paste_mode = True
                raw_line = []
                continue

        except KeyboardInterrupt:
            bridge.interrupt_requested = False
            try:
                write("\r\n")
                paste_mode = False
                mode_raw = False
                rl.init(">>> ")
            except Exception:
                pass
            continue
        except Exception as exc:
            _log_exc("repl loop", exc)
            try:
                write("\nstdio_sidecar: repl error (see logcat)\n")
                paste_mode = False
                mode_raw = False
                rl.init(">>> ")
            except Exception:
                pass
            continue


def _serve_client(conn):
    global _client_busy
    old_in, old_out, old_err = sys.stdin, sys.stdout, sys.stderr
    bridge = _SocketBridge(conn)
    _orig_sleep = _time_mod.sleep
    try:
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        bridge.start()
        mode = _read_mode_line(bridge)

        stdin = _BridgeStdin(bridge)
        stdout = _TeeTextIO(bridge.write_text, old_out)
        stderr = _TeeTextIO(bridge.write_text, old_err)
        sys.stdin = stdin
        sys.stdout = stdout
        sys.stderr = stderr

        if mode == "repl":
            # While the staged entry runs, only stdio is live (no >>>).
            try:
                bridge.interrupt_ident = threading.main_thread().ident
            except Exception:
                bridge.interrupt_ident = None
            if not _entry_done.is_set():
                try:
                    bridge.write_text(
                        "stdio attached; REPL starts when the script exits "
                        "(python -i style).\n"
                    )
                except Exception:
                    pass
                while not _entry_done.wait(0.05):
                    if bridge.closed:
                        return
                    # Discard typed input until the REPL owns the prompt.
                    while True:
                        ch = bridge.get_char(0)
                        if not ch:
                            break

            # Entry Ctrl-C sets interrupt_requested; clear it so the first idle
            # REPL poll does not print a second KeyboardInterrupt.
            bridge.interrupt_requested = False
            bridge.interrupt_ident = threading.get_ident()

            def _coop_sleep(seconds):
                if threading.get_ident() != bridge.interrupt_ident:
                    return _orig_sleep(seconds)
                end = _time_mod.perf_counter() + float(seconds)
                while True:
                    if bridge.interrupt_requested:
                        bridge.interrupt_requested = False
                        raise KeyboardInterrupt
                    remaining = end - _time_mod.perf_counter()
                    if remaining <= 0:
                        return None
                    _orig_sleep(min(0.05, remaining))

            _time_mod.sleep = _coop_sleep
            try:
                _run_mp_repl(bridge)
            finally:
                _time_mod.sleep = _orig_sleep
        else:
            try:
                bridge.interrupt_ident = threading.main_thread().ident
            except Exception:
                bridge.interrupt_ident = None
            try:
                bridge.write_text(
                    "PyDevices Android stdio attached (python %s).\n"
                    % ("%s.%s.%s" % sys.version_info[:3],)
                )
            except Exception:
                pass
            bridge.wait_closed()
    finally:
        _time_mod.sleep = _orig_sleep
        sys.stdin, sys.stdout, sys.stderr = old_in, old_out, old_err
        bridge.close()
        with _lock:
            _client_busy = False


def _accept_loop(sock):
    global _client_busy
    while True:
        try:
            conn, _addr = sock.accept()
        except Exception as exc:
            _log_exc("accept", exc)
            break
        with _lock:
            if _client_busy:
                try:
                    conn.sendall(b"BUSY\n")
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
                continue
            _client_busy = True
        try:
            _serve_client(conn)
        except Exception as exc:
            _log_exc("client", exc)
            with _lock:
                _client_busy = False


def mark_entry_done():
    """Call when staged ``run_entry`` returns (or there is no entry)."""
    _entry_done.set()


def start():
    """Start the localhost stdio listener once (no-op if already started)."""
    global _started
    if sys.platform != "android":
        return
    with _lock:
        if _started:
            return
        _started = True
    _install_thread_excepthook()
    # New process: staged entry has not finished yet.
    _entry_done.clear()
    port = _port()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((_HOST, port))
        sock.listen(1)
    except Exception as exc:
        _log_exc("bind %s:%s" % (_HOST, port), exc)
        try:
            sock.close()
        except Exception:
            pass
        with _lock:
            _started = False
        return
    print("stdio_sidecar: listening on %s:%s" % (_HOST, port), flush=True)
    thread = threading.Thread(
        target=_accept_loop, args=(sock,), name="stdio_sidecar", daemon=True
    )
    thread.start()

