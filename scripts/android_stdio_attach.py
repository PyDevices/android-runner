#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bidirectional TTY attach to the Android app stdio sidecar (via adb forward).

For ``MODE=repl``, puts the local TTY in raw mode (including while waiting to
connect) so Ctrl-C is ``\\x03`` rather than killing this process with
KeyboardInterrupt. MicroPython-style Ctrl-A/B/C/D/E are forwarded once
attached. Ctrl-\\ aborts connect or disconnects attach (app keeps running).

For ``MODE=stdio``, keeps line-oriented input; SIGINT sends ``\\x03``.
"""

from __future__ import annotations

import argparse
import os
import selectors
import signal
import socket
import sys
import time
import traceback

try:
    import termios
    import tty
except ImportError:  # Windows host — no termios; line mode only
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]


def _try_connect(host: str, port: int, mode: str, timeout: float = 1.0):
    """Open a session and send MODE=. Return connected socket or None."""
    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    sock.sendall(("MODE=%s\n" % mode).encode("utf-8"))
    sock.settimeout(0.35)
    try:
        probe = sock.recv(8, socket.MSG_PEEK)
    except socket.timeout:
        sock.settimeout(None)
        sock.setblocking(False)
        return sock
    except OSError:
        try:
            sock.close()
        except OSError:
            pass
        return None
    if not probe:
        try:
            sock.close()
        except OSError:
            pass
        return None
    if probe.startswith(b"BUSY"):
        try:
            sock.close()
        except OSError:
            pass
        return None
    sock.settimeout(None)
    sock.setblocking(False)
    return sock


def _drain_stdin(stdin_fd):
    """Non-blocking drain; return True if Ctrl-\\ seen (abort)."""
    abort = False
    if stdin_fd is None:
        return abort
    try:
        import fcntl

        fl = fcntl.fcntl(stdin_fd, fcntl.F_GETFL)
        fcntl.fcntl(stdin_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        try:
            while True:
                try:
                    chunk = os.read(stdin_fd, 256)
                except BlockingIOError:
                    break
                if not chunk:
                    break
                if b"\x1c" in chunk:
                    abort = True
        finally:
            fcntl.fcntl(stdin_fd, fcntl.F_SETFL, fl)
    except Exception:
        pass
    return abort


def _connect_loop(host, port, mode, retries, stdin_fd=None, raw_tty=False):
    """Retry connect. In raw TTY mode Ctrl-C is ignored; Ctrl-\\ aborts."""
    last_err = None
    # Suppress KeyboardInterrupt during wait (cooked stdin / non-raw fallback).
    def _hold_sigint(_signum, _frame):
        pass

    old_handler = signal.signal(signal.SIGINT, _hold_sigint)
    try:
        for attempt in range(max(1, retries)):
            if raw_tty and _drain_stdin(stdin_fd):
                print(
                    "\r\nandroid_stdio_attach: aborted (Ctrl-\\)",
                    file=sys.stderr,
                )
                return None
            try:
                sock = _try_connect(host, port, mode)
                if sock is not None:
                    return sock
                last_err = OSError("adb forward accepted but sidecar not ready")
            except OSError as exc:
                last_err = exc
            # Sleep in small slices so Ctrl-\\ / held SIGINT stay responsive.
            for _ in range(5):
                if raw_tty and _drain_stdin(stdin_fd):
                    print(
                        "\r\nandroid_stdio_attach: aborted (Ctrl-\\)",
                        file=sys.stderr,
                    )
                    return None
                time.sleep(0.05)
            if attempt == 8:
                # One-line hint after ~2s so Ctrl-C isn't mistaken for failure.
                sys.stderr.write(
                    "android_stdio_attach: waiting for app stdio on %s:%s "
                    "(Ctrl-\\ to abort)\r\n" % (host, port)
                )
                sys.stderr.flush()
    finally:
        try:
            signal.signal(signal.SIGINT, old_handler)
        except Exception:
            pass
    print(
        "android_stdio_attach: could not connect to %s:%s (%s)"
        % (host, port, last_err),
        file=sys.stderr,
    )
    return None


def _relay_stdio(sock, stdin_fd, sel):
    """Line-oriented relay (stdin cooked / SIGINT → \\x03)."""

    def _on_sigint(_signum, _frame):
        try:
            sock.sendall(b"\x03")
        except OSError:
            pass

    old_handler = signal.signal(signal.SIGINT, _on_sigint)
    try:
        while True:
            try:
                events = sel.select(timeout=0.5)
            except InterruptedError:
                continue
            for key, _mask in events:
                if key.fileobj is sock:
                    try:
                        data = sock.recv(4096)
                    except BlockingIOError:
                        continue
                    if not data:
                        return 0
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                elif key.fd == stdin_fd:
                    line = sys.stdin.buffer.readline()
                    if not line:
                        return 0
                    try:
                        sock.sendall(line)
                    except OSError:
                        return 0
    finally:
        try:
            signal.signal(signal.SIGINT, old_handler)
        except Exception:
            pass


def _relay_repl_raw(sock, stdin_fd, sel, restore_termios=None):
    """Byte relay; TTY already raw (or set here if restore_termios is None)."""
    assert termios is not None and tty is not None
    old = restore_termios
    owned = False
    if old is None:
        old = termios.tcgetattr(stdin_fd)
        tty.setraw(stdin_fd)
        owned = True
    try:
        while True:
            try:
                events = sel.select(timeout=0.5)
            except InterruptedError:
                continue
            for key, _mask in events:
                if key.fileobj is sock:
                    try:
                        data = sock.recv(4096)
                    except BlockingIOError:
                        continue
                    if not data:
                        return 0
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                elif key.fd == stdin_fd:
                    try:
                        chunk = os.read(stdin_fd, 256)
                    except OSError:
                        return 0
                    if not chunk:
                        return 0
                    # Ctrl-\ : leave attach (app continues).
                    if b"\x1c" in chunk:
                        return 0
                    try:
                        sock.sendall(chunk)
                    except OSError:
                        return 0
    finally:
        if owned or restore_termios is not None:
            try:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old)
            except Exception:
                pass
            try:
                sys.stdout.write("\r\n")
                sys.stdout.flush()
            except Exception:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host", default="127.0.0.1", help="forwarded localhost host"
    )
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument(
        "--mode",
        choices=("stdio", "repl"),
        default="stdio",
        help="MODE= handshake line sent to the app",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=80,
        help="connect attempts (~0.25s apart) waiting for the sidecar",
    )
    args = parser.parse_args(argv)

    stdin_fd = None
    try:
        stdin_fd = sys.stdin.fileno()
    except Exception:
        stdin_fd = None

    use_raw = (
        args.mode == "repl"
        and stdin_fd is not None
        and sys.stdin.isatty()
        and termios is not None
        and tty is not None
    )

    saved_termios = None
    if use_raw:
        # Raw before connect: Ctrl-C is a byte, not KeyboardInterrupt on sleep().
        saved_termios = termios.tcgetattr(stdin_fd)
        tty.setraw(stdin_fd)

    try:
        sock = _connect_loop(
            args.host,
            args.port,
            args.mode,
            args.retries,
            stdin_fd=stdin_fd,
            raw_tty=use_raw,
        )
        if sock is None:
            return 1

        sel = selectors.DefaultSelector()
        try:
            if stdin_fd is not None:
                sel.register(stdin_fd, selectors.EVENT_READ)
            sel.register(sock, selectors.EVENT_READ)

            if use_raw:
                # Relay restores termios; clear saved so outer finally is a no-op.
                saved = saved_termios
                saved_termios = None
                return _relay_repl_raw(sock, stdin_fd, sel, restore_termios=saved) or 0
            if stdin_fd is None:
                print(
                    "android_stdio_attach: stdin not usable",
                    file=sys.stderr,
                )
                return 1
            try:
                sys.stdin.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
            except Exception:
                pass
            return _relay_stdio(sock, stdin_fd, sel) or 0
        finally:
            try:
                sel.close()
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
    finally:
        if use_raw and saved_termios is not None:
            try:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, saved_termios)
            except Exception:
                pass
            try:
                sys.stdout.write("\r\n")
                sys.stdout.flush()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        # Last-resort: never dump a traceback for Ctrl-C during attach.
        try:
            sys.stdout.write("\r\n")
            sys.stdout.flush()
        except Exception:
            pass
        sys.exit(130)
    except Exception:
        # Unexpected host-side failure — keep hot-path I/O mute; dump once here.
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
