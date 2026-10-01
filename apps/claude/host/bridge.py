#!/usr/bin/env python3
"""claude-c128 bridge: run Claude Code on Linux, display it on a real C128.

Spawns Claude Code in an 80x25 PTY, emulates the terminal, converts each frame
to PETSCII screen codes, and ships only the changed cells over a serial link to
the C128. Keystrokes come back the other way.

Transports:
  --connect HOST:PORT   dial the Ultimate II+ modem listener (real hardware)
  --listen PORT         wait for a client (VICE's -rsdev1 points here)
  --stdio               run the client model locally, for development

Example, against the real machine:
  python3 server/bridge.py --connect ULTIMATE-IP:3000
"""
import argparse
import errno
import logging
import unicodedata
import fcntl
import os
import pty
import select
import shlex
import signal
import socket
import struct
import sys
import termios
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import keymap                       # noqa: E402
import font                         # noqa: E402
import petscii                      # noqa: E402
import protocol                     # noqa: E402
from vtscreen import VTScreen       # noqa: E402

# The C128 renders on the 80-column VDC; the C64 has only the VIC-II's 40-column
# screen. Claude Code lays itself out to whatever width the PTY reports, so the
# machine choice propagates from here into the terminal, the differ and the
# child process alike.
COLS, ROWS = 80, 25
MACHINES = {
    "c128": {"cols": 80, "rows": 25, "panel": True},
    "c64":  {"cols": 40, "rows": 25, "panel": False},
}

log = logging.getLogger("claude-c128")

# How often unmapped characters are reported. The renderer records every one it
# could not draw; without this they would only show up as a question mark on a
# screen nobody is reading at the time.
UNMAPPED_INTERVAL = 30.0


def setup_logging(path, level):
    """Log to a file, and to stderr so systemd's journal gets it too."""
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    root = logging.getLogger("claude-c128")
    root.setLevel(level)
    root.handlers.clear()
    if path:
        fh = logging.FileHandler(path)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    return root

# Frames are coalesced for this long before being sent. Claude Code repaints
# far faster than a serial line can carry, and the eye cannot see 30ms anyway.
FRAME_INTERVAL = 0.05

# How often the companion screen's clock and spinner refresh.
PANEL_INTERVAL = 1.0

# If this much output is still queued, the link is behind. Drop the backlog and
# force a full repaint rather than displaying an ever-staler screen.
BACKLOG_LIMIT = 32768


class PtyProcess:
    def __init__(self, argv, cols=COLS, rows=ROWS, cwd=None):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.environ["TERM"] = "xterm-256color"
            os.environ["COLUMNS"] = str(cols)
            os.environ["LINES"] = str(rows)
            # Claude Code suppresses its own TUI when it thinks it is nested.
            os.environ.pop("CLAUDECODE", None)
            os.environ.pop("CLAUDE_CODE_SSE_PORT", None)
            if cwd:
                os.chdir(cwd)
            os.execvp(argv[0], argv)
        self.pending = bytearray()
        self.reaped = False
        self.resize(cols, rows)
        flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
        fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def resize(self, cols, rows):
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                    struct.pack("HHHH", rows, cols, 0, 0))

    def read(self, size=65536):
        try:
            return os.read(self.fd, size)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return b""
            return None                     # EIO: the child exited
        return b""

    def write(self, data):
        self.pending.extend(data)
        self.flush()

    def flush(self):
        if self.pending:
            try:
                count = os.write(self.fd, self.pending)
            except (BlockingIOError, InterruptedError):
                return
            del self.pending[:count]

    def alive(self):
        if self.reaped:
            return False
        try:
            pid, _ = os.waitpid(self.pid, os.WNOHANG)
            self.reaped = pid != 0
            return not self.reaped
        except ChildProcessError:
            self.reaped = True
            return False

    def close(self):
        # pty.fork creates a child session/process group; only signal that group.
        # Never signal a reaped PID, which may have been reused by the host.
        if not self.reaped:
            for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(self.pid, sig)
                except ProcessLookupError:
                    break
                deadline = time.monotonic() + 0.2
                while time.monotonic() < deadline and self.alive():
                    time.sleep(0.01)
                if self.reaped:
                    break
            if not self.reaped:
                try:
                    os.waitpid(self.pid, 0)
                except ChildProcessError:
                    pass
                self.reaped = True
        try:
            os.close(self.fd)
        except OSError:
            pass


class SerialLink:
    """A byte pipe to the C128, with a bounded outgoing queue and pacing.

    Neither VICE's RS232 emulation nor the Ultimate's TCP-backed modem
    rate-limits to the ACIA's nominal baud: both will hand over data as fast as
    the socket delivers it. The C128 receives into a 256-byte ring from NMI, and
    a burst larger than that is simply lost — which shows up as a screen missing
    whole rows, not as an error. So the sender meters itself to the real link
    speed instead of trusting the transport to do it.
    """

    def __init__(self, sock, byte_rate=3840):
        self.sock = sock
        self.sock.setblocking(False)
        self.out = bytearray()
        self.overflowed = False
        self.byte_rate = byte_rate          # 38400 baud 8N1 = 3840 bytes/sec
        self.allowance = float(byte_rate)
        self.last_tick = time.time()
        # Bytes the client has room for. Credits arrive as it consumes.
        self.credits = protocol.CREDIT_WINDOW

    def fileno(self):
        return self.sock.fileno()

    def queue(self, data):
        if len(self.out) + len(data) > BACKLOG_LIMIT:
            self.out.clear()
            self.overflowed = True
            return False
        self.out += data
        return True

    def wants_write(self):
        return bool(self.out)

    def flush(self):
        if not self.out:
            return
        now = time.time()
        self.allowance = min(
            float(self.byte_rate),                      # at most one second of credit
            self.allowance + (now - self.last_tick) * self.byte_rate,
        )
        self.last_tick = now
        budget = min(int(self.allowance), self.credits)
        if budget < 1:
            return
        try:
            sent = self.sock.send(self.out[:budget])
            del self.out[:sent]
            self.allowance -= sent
            self.credits -= sent
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            raise ConnectionError("serial link closed while writing")

    def recv(self):
        try:
            data = self.sock.recv(4096)
        except (BlockingIOError, InterruptedError):
            return b""
        except OSError:
            raise ConnectionError("serial link closed while reading")
        if not data:
            raise ConnectionError("serial link closed by peer")
        return data

    def add_credit(self, units=1):
        self.credits = min(protocol.CREDIT_WINDOW,
                           self.credits + units * protocol.CREDIT_UNIT)

    def reset_credit(self):
        self.credits = protocol.CREDIT_WINDOW

    def take_overflow(self):
        was, self.overflowed = self.overflowed, False
        return was

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# VIC-II colour codes for the companion screen.
VIC_CYAN, VIC_WHITE, VIC_GREY, VIC_GREEN, VIC_YELLOW, VIC_RED = 3, 1, 15, 13, 7, 10

SPINNER = "|/-\\"


def panel_lines(title, busy, tick, uptime, frames, kbytes, drops):
    """Content for the 40-column companion screen, as (row, colour, text).

    Deliberately shows what the bridge actually knows - the title Claude Code
    sets, and the state of the link - rather than trying to parse meaning out
    of the TUI, which would be guesswork that quietly goes stale.
    """
    mark = SPINNER[tick % len(SPINNER)] if busy else "."
    mins, secs = divmod(int(uptime), 60)
    return [
        (0, VIC_CYAN,  "claude code".ljust(28) + "c128 term"),
        (1, VIC_GREY,  "-" * 40),
        (3, VIC_WHITE, f"{mark} {title}"[:40]),
        (5, VIC_GREY,  f"session   {mins:d}m{secs:02d}s"),
        (6, VIC_GREY,  f"frames    {frames}"),
        (7, VIC_GREY,  f"link      {kbytes:.1f} kb"),
        (8, VIC_RED if drops else VIC_GREEN,
                       f"dropped   {drops}" if drops else "receiver drops: not reported"),
        (10, VIC_GREY, "-" * 40),
        (11, VIC_YELLOW, "HELP repaints / reconnects"),
        (12, VIC_GREY, "F8 returns to the Kestrel desktop"),
    ]


class ClientClosed(ConnectionError):
    """The user explicitly closed the native terminal."""


class Bridge:
    def __init__(self, link, argv, cwd=None, panel=True, verbose=False,
                 cols=COLS, rows=ROWS, machine="c128"):
        # The two machines have different palettes, so the colour tables have to
        # be selected before the first frame is rendered. Same index, different
        # colour: VDC 12 is a brown, VIC-II 12 is a medium grey.
        self.palette = petscii.use_machine(machine)
        self.machine = machine
        self.link = link
        self.cols = cols
        self.rows = rows
        self.vt = VTScreen(cols, rows)
        self.differ = protocol.ScreenDiffer(cols, rows)
        self.argv, self.cwd = argv, cwd
        self.proc = None
        self.panel_enabled = panel
        self.verbose = verbose
        self.last_frame = 0.0
        self.dirty = False
        self.last_panel = {}
        self.started = time.time()
        self.last_activity = 0.0
        self.last_panel_time = 0.0
        self.last_unmapped = 0.0
        self.bytes_out = 0
        self.frames_sent = 0
        self.pending_escape = False
        self.client_closed = False
        self.paste_negotiated = False
        self.input_packet = None
        self.paste_expected = 0
        self.paste_data = bytearray()
        self.paste_invalid = False

        # Nothing is sent until the client announces itself. The transport
        # buffers whatever is written before the C128 has opened its ACIA, then
        # delivers it in one burst that overruns the receive ring - which loses
        # whole rows silently. Waiting for the client's resync request makes the
        # first byte on the wire also the first byte it can receive.
        self.client_ready = False

    def _report_unmapped(self):
        """Log characters the renderer could not draw, once per batch.

        These are the real coverage gaps: anything the block sweep in
        tools/charaudit.py does not know about shows up here the first time it
        appears on screen, with its codepoint and Unicode name so it can be
        fixed rather than guessed at.
        """
        misses = petscii.take_unmapped()
        if not misses:
            return
        for ch, n in sorted(misses.items(), key=lambda kv: -kv[1]):
            log.warning("unmapped character U+%04X %s x%d -> rendered as '?'",
                        ord(ch), unicodedata.name(ch, "(unnamed)"), n)

    def _take_control(self, data, *, translated=False):
        """Parse control packets across reads; preserve key/paste ordering.

        Clipboard payloads are length framed, so embedded zeroes never become
        control opcodes. A complete paste is emitted only at END. The regular
        key path retains PETSCII translation; clipboard text is already ASCII.
        """
        out = bytearray()
        for byte in data:
            packet = getattr(self, "input_packet", None)
            if packet is not None:
                kind, count, body = packet
                body.append(byte)
                if len(body) == count:
                    self.input_packet = None
                    self._paste_packet(kind, bytes(body))
                continue
            if self.pending_escape:
                self.pending_escape = False
                out.extend(self._control(byte) or b"")
            elif byte == protocol.CLIENT_ESCAPE:
                self.pending_escape = True
            elif not getattr(self, "paste_expected", 0):
                out.extend(keymap.petscii_to_bytes(byte) if translated else bytes([byte]))
        return bytes(out)

    def _paste_packet(self, kind, body):
        if kind == "begin":
            size = int.from_bytes(body, "little")
            self.paste_expected = size or -1
            self.paste_data = bytearray()
            self.paste_invalid = not (getattr(self, "paste_negotiated", False)
                and self.client_ready and not self.client_closed and 1 <= size <= protocol.MAX_PASTE)
        elif kind == "count":
            count = body[0]
            if not 1 <= count <= 64:
                self.paste_invalid = True
            if count:
                self.input_packet = ("data", count, bytearray())
        elif kind == "data":
            if (getattr(self, "paste_invalid", True) or not self.paste_expected
                    or len(self.paste_data) + len(body) > self.paste_expected):
                self.paste_invalid = True
            else:
                self.paste_data.extend(body)

    def _paste_end(self):
        data = bytes(getattr(self, "paste_data", b""))
        valid = (getattr(self, "paste_negotiated", False) and self.client_ready
            and not self.client_closed and not getattr(self, "paste_invalid", True)
            and len(data) == getattr(self, "paste_expected", 0) and bool(data)
            and all(byte in (9, 10, 13) or 32 <= byte <= 126 for byte in data))
        self.paste_expected = 0
        self.paste_data = bytearray()
        self.paste_invalid = False
        if getattr(self, "paste_negotiated", False):
            self.link.queue(bytes([protocol.CMD_PASTE_RESULT, 0 if valid else 1]))
        if not valid:
            return b""
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        return b"\x1b[200~" + data + b"\x1b[201~"

    def _control(self, code):
        if self.client_closed and code != protocol.CLIENT_CREDIT:
            return
        if code == protocol.CLIENT_CAPABILITIES:
            if self.client_ready:
                self.paste_negotiated = True
                self.link.queue(bytes([protocol.CMD_CAPABILITIES, protocol.FEATURE_PASTE]))
        elif code == protocol.CLIENT_PASTE_BEGIN:
            self.input_packet = ("begin", 2, bytearray())
        elif code == protocol.CLIENT_PASTE_CHUNK:
            self.input_packet = ("count", 1, bytearray())
        elif code == protocol.CLIENT_PASTE_END:
            return self._paste_end()
        elif code == protocol.CLIENT_PASTE_ABORT:
            self.paste_expected = 0
            self.paste_data = bytearray()
            self.paste_invalid = False
        elif code == protocol.CLIENT_RESYNC:
            if not self.client_ready:
                # An Ultimate listener can accept TCP and immediately report
                # an offline modem. Start the host program only when the C128
                # has opened its serial port and completed the handshake.
                self.proc = PtyProcess(self.argv, self.cols, self.rows, self.cwd)
                self.client_ready = True
                enc = protocol.Encoder()
                enc.hello(self.cols, self.rows)
                # Redefine the VDC characters Claude Code needs and PETSCII
                # lacks, before anything is drawn with them.
                for code, bitmap in font.definitions():
                    enc.glyph(code, bitmap)
                self.link.queue(enc.take())
                if self.verbose:
                    log.info("client is listening")
            # Deliberately does NOT restore the credit window. The client's
            # receive ring may still hold unread bytes; handing back a full
            # window on top of those is exactly how it overruns. Credit is
            # returned only as the client actually consumes.
            self.differ.reset()
            self.dirty = True
            self.last_panel = {}
            if self.verbose:
                log.info("client asked for a resync")
        elif code == protocol.CLIENT_CREDIT:
            self.link.add_credit()
        elif code == protocol.CLIENT_BYE:
            # Finish parsing this receive batch: credits after BYE still count
            # while queued protocol commands drain ahead of our BYE reply.
            self.client_closed = True
            self.paste_expected = 0
            self.paste_data = bytearray()

    def _send_frame(self):
        if self.link.take_overflow():
            # We fell behind; resynchronise from a clean slate.
            self.differ.reset()
            if self.verbose:
                log.warning("link backlog exceeded, forcing full repaint")

        frame = self.differ.diff(self.vt.grid(), self.vt.cursor())

        if self.vt.take_bell():
            enc = protocol.Encoder()
            enc.bell()
            frame += enc.take()

        if self.panel_enabled:
            frame += self._panel_frame()
            self.last_panel_time = time.time()

        # A bare FRAME byte means nothing changed; do not spend the link on it.
        if len(frame) > 1:
            self.link.queue(frame)
            self.bytes_out += len(frame)
            self.frames_sent += 1
        self.dirty = False
        self.last_frame = time.time()

    def _panel_frame(self):
        title = self.vt.title() or "claude code"
        busy = time.time() - self.last_activity < 1.0
        lines = panel_lines(
            title, busy, self.frames_sent,
            time.time() - self.started, self.frames_sent,
            self.bytes_out / 1024.0,
            0,
        )
        # Only resend rows that changed: the panel shares the link with the
        # terminal, and a clock ticking every second must not cost 400 bytes.
        enc = protocol.Encoder()
        changed = False
        for row, color, text in lines:
            text = text.ljust(40)[:40]
            if self.last_panel.get(row) == (color, text):
                continue
            self.last_panel[row] = (color, text)
            enc.panel(row, color, [petscii.to_screen_code(c) for c in text])
            changed = True
        return enc.take() if changed else b""

    def run(self):
        """Returns True for a clean exit (claude quit on its own), False for a
        link failure. Distinct so a supervisor (systemd) can restart on a
        dropped link without respawning claude every time a session ends."""
        clean = True
        try:
            while True:
                if self.proc is not None and not self.proc.alive():
                    while True:
                        tail = self.proc.read()
                        if not tail: break
                        self.vt.feed(tail)
                        self.dirty = True
                    if self.verbose:
                        log.info("claude exited")
                    break

                rlist = [self.link]
                if self.proc is not None:
                    rlist.append(self.proc.fd)
                wlist = [self.link] if self.link.wants_write() else []
                if self.proc is not None and self.proc.pending:
                    wlist.append(self.proc.fd)
                if self.link.wants_write():
                    timeout = 0.02          # keep the paced writer moving
                elif self.dirty:
                    timeout = FRAME_INTERVAL
                else:
                    timeout = min(0.25, PANEL_INTERVAL)
                r, w, _ = select.select(rlist, wlist, [], timeout)

                if self.proc is not None and self.proc.fd in r:
                    data = self.proc.read()
                    if data is None:
                        break
                    if data:
                        self.vt.feed(data)
                        self.dirty = True
                        self.last_activity = time.time()

                if self.link in r:
                    keys = self.link.recv()
                    if keys:
                        typed = self._take_control(keys, translated=True)
                        if self.client_closed:
                            raise ClientClosed("client returned to Kestrel")
                        # Before the client announces itself, anything arriving
                        # is the Ultimate's modem chatter ("Welcome to the Modem
                        # Emulation Layer...", "CONNECT 38400"), not keystrokes.
                        if self.client_ready and typed:
                            out = typed
                            log.debug("keys from C128: %r -> pty %r", typed, out)
                            self.proc.write(out)
                        elif typed:
                            log.debug("dropped pre-handshake bytes: %r", typed)

                now = time.time()
                if now - self.last_unmapped >= UNMAPPED_INTERVAL:
                    self.last_unmapped = now
                    self._report_unmapped()
                if (self.client_ready and self.dirty
                        and now - self.last_frame >= FRAME_INTERVAL):
                    self._send_frame()
                elif (self.client_ready and self.panel_enabled
                        and now - self.last_panel_time >= PANEL_INTERVAL):
                    # The companion screen has a clock and a spinner, so it
                    # ticks even while the terminal itself is idle. Only rows
                    # that changed go on the wire.
                    panel = self._panel_frame()
                    if panel:
                        self.link.queue(panel)
                        self.bytes_out += len(panel)
                    self.last_panel_time = now

                if self.proc is not None and self.proc.fd in w:
                    self.proc.flush()
                if self.link in w or self.link.wants_write():
                    self.link.flush()
        except ClientClosed as exc:
            self.client_closed = True
            log.info("%s", exc)
        except ConnectionError as exc:
            log.warning("link: %s", exc)
            clean = False
        except KeyboardInterrupt:
            pass
        finally:
            if self.client_ready or self.client_closed:
                try:
                    if self.dirty and not self.client_closed:
                        self._send_frame()
                    enc = protocol.Encoder()
                    enc.bye()
                    # At most two extra bytes beyond the normal backlog cap.
                    # queue() can discard a full queue; that would truncate a
                    # command whose prefix is already on the wire and hide BYE
                    # inside its payload. Preserve the entire pending stream.
                    self.link.out.extend(enc.take())
                    # Finish complete frames before BYE; continue accepting
                    # returned receive credits while the client drains its ring.
                    deadline = time.monotonic() + 15.0
                    while self.link.out and time.monotonic() < deadline:
                        self.link.flush()
                        if not self.link.out:
                            break
                        readable, _, _ = select.select([self.link], [], [], 0.01)
                        if readable:
                            self._take_control(self.link.recv())
                    if self.link.out:
                        clean = False
                        log.warning("timed out draining terminal shutdown")
                except (ConnectionError, OSError):
                    if not self.client_closed:
                        clean = False
            if self.proc is not None:
                self.proc.close()
            self.link.close()
            log.info("session end: %d frames, %d bytes, %d scrolls",
                     self.frames_sent, self.bytes_out, self.differ.scrolls_used)
        return clean


def open_transport(args):
    if args.connect:
        host, _, port = args.connect.rpartition(":")
        sock = socket.create_connection((host, int(port)), timeout=15)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        log.info("connected to %s", args.connect)
        return sock
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", args.listen))
    listener.listen(1)
    log.info("listening on 127.0.0.1:%d", args.listen)
    sock, peer = listener.accept()
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    listener.close()
    log.info("client connected from %s", peer)
    return sock


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--connect", metavar="HOST:PORT",
                   help="dial the Ultimate II+ modem listener")
    g.add_argument("--listen", type=int, metavar="PORT",
                   help="wait for a client on 127.0.0.1:PORT (VICE)")
    p.add_argument("--command", default="claude",
                   help="what to run in the PTY (default: claude)")
    p.add_argument("--cwd", help="working directory for the child")
    p.add_argument("--machine", choices=sorted(MACHINES), default="c128",
                   help="target machine: c128 uses the 80-column VDC and the "
                        "40-column screen as a status panel; c64 uses the "
                        "40-column screen as the terminal and has no panel")
    p.add_argument("--no-panel", action="store_true",
                   help="do not drive the 40-column companion screen")
    p.add_argument("--rate", type=int, default=3840,
                   help="link speed in bytes/sec (38400 baud 8N1 = 3840)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--log-file", default=None,
                   help="write the session log here as well as to stderr")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = p.parse_args()
    if args.rate <= 0:
        p.error("--rate must be positive")
    def terminate_session(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate_session)

    setup_logging(args.log_file,
                  "DEBUG" if args.verbose else args.log_level)
    sock = open_transport(args)
    machine = MACHINES[args.machine]
    bridge = Bridge(SerialLink(sock, byte_rate=args.rate), shlex.split(args.command),
                    cwd=args.cwd,
                    panel=machine["panel"] and not args.no_panel,
                    verbose=args.verbose,
                    cols=machine["cols"], rows=machine["rows"],
                    machine=args.machine)
    # 0 for claude exiting on its own (nothing left to serve, do not respawn);
    # 1 for a link failure, so a supervisor like systemd knows to restart and
    # let the C128 dial back in.
    return 0 if bridge.run() else 1


if __name__ == "__main__":
    raise SystemExit(main())
